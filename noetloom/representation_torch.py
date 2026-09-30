"""Optional own-initialized field structuring and solver; no task decoder or scorer access."""
from __future__ import annotations

import math
import random

import torch
from torch import nn
from torch.nn import functional as F

from .contracts import ContractError
from .representation_common import parameter_count, shapes, validate_parameters


class Layer(nn.Module):
    def __init__(self, inputs: int, outputs: int, nonlinear: bool, generator: torch.Generator):
        super().__init__()
        self.weight = nn.Parameter(torch.randn(outputs, inputs, generator=generator) / math.sqrt(inputs))
        self.bias = nn.Parameter(torch.zeros(outputs))
        self.nonlinear = nonlinear

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        result = F.linear(values, self.weight, self.bias)
        return torch.tanh(result) if self.nonlinear else result

    def artifact(self) -> dict:
        return {"input_dim": self.weight.shape[1], "output_dim": self.weight.shape[0],
                "weights": self.weight.detach().flatten().tolist(), "bias": self.bias.detach().tolist(),
                "activation": "tanh" if self.nonlinear else "identity"}


class Model(nn.Module):
    def __init__(self, arm: str, seed: int):
        super().__init__()
        self.arm, self.seed = arm, seed
        construction, solver = shapes(arm)
        generator = torch.Generator(device="cpu").manual_seed(seed ^ 0xC011)
        self.construction = nn.ModuleList([Layer(i, o, index == 0, generator)
                                           for index, (i, o) in enumerate(construction)])
        if arm == "static":
            self.static_scores = nn.Parameter(torch.randn(16, 64, generator=generator) / math.sqrt(64))
        else:
            self.register_parameter("static_scores", None)
        generator = torch.Generator(device="cpu").manual_seed(seed)
        self.solver = nn.ModuleList([Layer(i, o, index < 2, generator)
                                    for index, (i, o) in enumerate(solver)])
        if sum(p.numel() for p in self.parameters()) != parameter_count(arm):
            raise ContractError("tensor parameter count differs from registration")

    def construct(self, values: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor | None]:
        if (values.ndim != 2 or values.shape[1] != 64 or not torch.isfinite(values).all()
                or (values.abs() > 2).any()):
            raise ContractError("construction requires bounded 64-scalar fields")
        if self.arm.startswith("fixed_"):
            return values, None
        if self.arm == "conditional":
            scores = values
            for layer in self.construction:
                scores = layer(scores)
            scores = scores.reshape(-1, 16, 64)
        else:
            scores = self.static_scores.expand(len(values), -1, -1)
        matrix = torch.softmax(scores, dim=2)
        return torch.bmm(matrix, values.unsqueeze(2)).squeeze(2), matrix

    def solve(self, intermediate: torch.Tensor) -> torch.Tensor:
        result = intermediate
        for layer in self.solver:
            result = layer(result)
        return result

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        intermediate, _ = self.construct(values)
        return self.solve(intermediate)

    def artifact(self, step: int) -> dict:
        result = {"schema_version": "noetloom.representation_parameters.v1", "arm": self.arm,
                  "seed": self.seed, "step": step,
                  "construction": [layer.artifact() for layer in self.construction],
                  "static_scores": [] if self.static_scores is None else self.static_scores.detach().flatten().tolist(),
                  "solver": [layer.artifact() for layer in self.solver]}
        validate_parameters(result)
        return result

    @classmethod
    def from_artifact(cls, value: dict) -> "Model":
        validate_parameters(value)
        result = cls(value["arm"], value["seed"])
        with torch.no_grad():
            for group in ("construction", "solver"):
                for layer, raw in zip(getattr(result, group), value[group]):
                    layer.weight.copy_(torch.tensor(raw["weights"]).reshape_as(layer.weight))
                    layer.bias.copy_(torch.tensor(raw["bias"]))
            if result.static_scores is not None:
                result.static_scores.copy_(torch.tensor(value["static_scores"]).reshape(16, 64))
        return result


def optimizer(model: Model) -> torch.optim.Optimizer:
    return torch.optim.Adam(model.parameters(), lr=0.003, betas=(0.9, 0.999), eps=1e-8,
                            weight_decay=0.0, foreach=False, fused=False)


def update(model: Model, opt: torch.optim.Optimizer, values: torch.Tensor,
           targets: torch.Tensor, indices: list[int]) -> float:
    opt.zero_grad(set_to_none=True)
    loss = F.cross_entropy(model(values[indices]), targets[indices])
    if not torch.isfinite(loss):
        raise ContractError("nonfinite representation loss")
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
    opt.step()
    return float(loss.detach())


def sample_indices(seed: int, steps: int, count: int) -> list[list[int]]:
    rng = random.Random(seed ^ 22109)
    return [[rng.randrange(count) for _ in range(6)] for _ in range(steps)]


def infer(model: Model, values: torch.Tensor, shift_group: int = 0) -> dict:
    with torch.no_grad():
        intermediate, matrices = model.construct(values)
        if shift_group:
            if model.arm != "conditional" or shift_group < 2 or len(values) % shift_group:
                raise ContractError("shifted-map intervention requires complete conditional groups")
            matrices = matrices.reshape(-1, shift_group, 16, 64).roll(1, dims=1).reshape(-1, 16, 64)
            intermediate = torch.bmm(matrices, values.unsqueeze(2)).squeeze(2)
        logits = model.solve(intermediate)
        entropy = None if matrices is None else -(matrices * matrices.clamp_min(torch.finfo(matrices.dtype).tiny).log()).sum(2).mean().item()
        variance = None if matrices is None else matrices.var(0, unbiased=False).mean().item()
    return {"logits": logits.tolist(), "predictions": logits.argmax(1).tolist(),
            "intermediates": intermediate.tolist(), "transport_entropy": entropy,
            "transport_variance": variance}


def check_gradients() -> dict:
    """Sample every parameter tensor on a smooth artificial field, not any scored split."""
    model = Model("conditional", 712).double()
    generator = torch.Generator().manual_seed(731)
    values = torch.randn(6, 64, generator=generator, dtype=torch.float64).tanh()
    targets = torch.tensor([0, 1, 0, 1, 1, 0])
    F.cross_entropy(model(values), targets).backward()
    maximum, checked = 0.0, 0
    for parameter in model.parameters():
        for index in sorted({0, parameter.numel() // 2, parameter.numel() - 1}):
            exact = parameter.grad.flatten()[index].item()
            original = parameter.detach().flatten()[index].item()
            with torch.no_grad():
                parameter.flatten()[index] = original + 1e-5
                plus = F.cross_entropy(model(values), targets).item()
                parameter.flatten()[index] = original - 1e-5
                minus = F.cross_entropy(model(values), targets).item()
                parameter.flatten()[index] = original
            maximum = max(maximum, abs(exact - (plus - minus) / 2e-5))
            checked += 1
    if maximum > 1e-7:
        raise ContractError("representation finite-difference gradient check failed")
    return {"checked_scalars": checked, "maximum_absolute_error": maximum,
            "scope": "sampled entries across all conditional parameter tensors, synthetic smooth loss"}
