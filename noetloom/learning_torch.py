"""Optional training backend for EXP-0002; never imported by the stdlib harness."""
from __future__ import annotations

import math
import random
from typing import Any

import torch
from torch import nn
from torch.nn import functional as F

from .contracts import ContractError


def configure() -> dict[str, Any]:
    if torch.__version__.split("+")[0] != "2.14.0":
        raise ContractError("EXP-0002 requires the registered PyTorch 2.14.0 backend")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    return {"torch": torch.__version__, "device": "cpu", "dtype": "float32", "threads": 1,
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled()}


class CellModel(nn.Module):
    def __init__(self, seed: int, arm: str):
        super().__init__()
        if arm not in {"selective", "dense", "frozen_routing", "no_history"}:
            raise ContractError("unknown learning arm")
        self.seed, self.arm = seed, arm
        generator = torch.Generator(device="cpu").manual_seed(seed)

        def matrix(rows: int, cols: int) -> nn.Parameter:
            return nn.Parameter(torch.randn(rows, cols, generator=generator) / math.sqrt(cols))

        self.query = matrix(8, 16)
        self.key = matrix(8, 16)
        self.encoder = matrix(8, 5)
        self.encoder_bias = nn.Parameter(torch.zeros(8))
        self.decoder = matrix(5, 8)
        self.decoder_bias = nn.Parameter(torch.zeros(5))
        self.age = nn.Parameter(torch.zeros(()))
        self.null_score = nn.Parameter(torch.zeros(()))
        self.null_payload = nn.Parameter(torch.zeros(8))
        if arm in {"frozen_routing", "no_history"}:
            for parameter in (self.query, self.key, self.age, self.null_score):
                parameter.requires_grad_(False)
        if arm == "no_history":
            self.encoder.requires_grad_(False)
            self.encoder_bias.requires_grad_(False)

    def forward(self, views: dict[str, torch.Tensor]) -> torch.Tensor:
        if set(views) != {"query", "keys", "inputs", "ages", "mask"}:
            raise ContractError("predictor inputs must contain observations only")
        count = views["query"].shape[0]
        if self.arm == "no_history":
            read = self.null_payload.unsqueeze(0).expand(count, -1)
        else:
            query = F.linear(views["query"], self.query)
            keys = F.linear(views["keys"], self.key)
            scores = (keys * query.unsqueeze(1)).sum(-1) / math.sqrt(8) + self.age * views["ages"]
            scores = scores.masked_fill(~views["mask"], -1e9)
            scores = torch.cat((self.null_score.expand(count, 1), scores), dim=1)
            soft = torch.softmax(scores, dim=1)
            if self.arm == "dense":
                selection = soft
            else:
                hard = F.one_hot(scores.argmax(dim=1), num_classes=33).to(soft.dtype)
                selection = hard - soft.detach() + soft
            values = torch.tanh(F.linear(views["inputs"], self.encoder, self.encoder_bias))
            payloads = torch.cat((self.null_payload.expand(count, 1, 8), values), dim=1)
            read = (selection.unsqueeze(-1) * payloads).sum(dim=1)
        return F.linear(read, self.decoder, self.decoder_bias)

    def artifact(self, step: int) -> dict[str, Any]:
        def affine(weights: torch.Tensor, bias: torch.Tensor | None, activation: str) -> dict:
            return {"input_dim": weights.shape[1], "output_dim": weights.shape[0],
                    "weights": weights.detach().flatten().tolist(),
                    "bias": bias.detach().tolist() if bias is not None else [0.0] * weights.shape[0],
                    "activation": activation}
        return {"schema_version": "noetloom.cell_parameters.v1", "arm": self.arm,
                "seed": self.seed, "step": step,
                "query": affine(self.query, None, "identity"),
                "key": affine(self.key, None, "identity"),
                "encoder": affine(self.encoder, self.encoder_bias, "tanh"),
                "decoder": affine(self.decoder, self.decoder_bias, "identity"),
                "age_coefficient": self.age.item(), "null_score": self.null_score.item(),
                "null_payload": self.null_payload.detach().tolist()}

    @classmethod
    def from_artifact(cls, artifact: dict[str, Any]) -> "CellModel":
        if artifact["schema_version"] != "noetloom.cell_parameters.v1":
            raise ContractError("unknown parameter artifact")
        model = cls(artifact["seed"], artifact["arm"])
        with torch.no_grad():
            for name in ("query", "key", "encoder", "decoder"):
                matrix = getattr(model, name)
                matrix.copy_(torch.tensor(artifact[name]["weights"]).reshape(matrix.shape))
            model.encoder_bias.copy_(torch.tensor(artifact["encoder"]["bias"]))
            model.decoder_bias.copy_(torch.tensor(artifact["decoder"]["bias"]))
            model.age.copy_(torch.tensor(artifact["age_coefficient"]))
            model.null_score.copy_(torch.tensor(artifact["null_score"]))
            model.null_payload.copy_(torch.tensor(artifact["null_payload"]))
        return model


def tensor_views(prefixes: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
    count = len(prefixes)
    keys = torch.zeros(count, 32, 16)
    inputs = torch.zeros(count, 32, 5)
    ages = torch.zeros(count, 32)
    mask = torch.zeros(count, 32, dtype=torch.bool)
    for index, prefix in enumerate(prefixes):
        events = prefix["events"]
        if events:
            keys[index, :len(events)] = torch.tensor([e["key"] for e in events])
            inputs[index, :len(events)] = torch.tensor([e["input"] for e in events])
            ages[index, :len(events)] = torch.tensor([math.log1p(prefix["writes"] - e["written_at"])
                                                    for e in events])
            mask[index, :len(events)] = True
    return {"query": torch.tensor([p["key"] for p in prefixes]), "keys": keys,
            "inputs": inputs, "ages": ages, "mask": mask,
            "targets": torch.tensor([p["expected"] for p in prefixes], dtype=torch.long)}


def batch(views: dict[str, torch.Tensor], indices: list[int]) -> dict[str, torch.Tensor]:
    return {key: value[indices] for key, value in views.items()}


def features(views: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: value for key, value in views.items() if key != "targets"}


def optimizer(model: CellModel) -> torch.optim.Optimizer:
    return torch.optim.Adam((p for p in model.parameters() if p.requires_grad),
                            lr=0.02, betas=(0.9, 0.999), eps=1e-8, weight_decay=0.0,
                            foreach=False, fused=False)


def update(model: CellModel, opt: torch.optim.Optimizer, views: dict[str, torch.Tensor]) -> float:
    opt.zero_grad(set_to_none=True)
    loss = F.cross_entropy(model(features(views)), views["targets"])
    if not torch.isfinite(loss):
        raise ContractError("non-finite learning loss")
    loss.backward()
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
    if not torch.isfinite(norm):
        raise ContractError("non-finite learning gradient")
    opt.step()
    return float(loss.detach())


def evaluate(model: CellModel, views: dict[str, torch.Tensor]) -> dict[str, Any]:
    with torch.no_grad():
        logits = torch.cat([model({key: value[start:start + 128] for key, value in features(views).items()})
                            for start in range(0, len(views["targets"]), 128)])
        loss = float(F.cross_entropy(logits, views["targets"]))
    return {"cross_entropy": loss, "logits": logits.tolist(),
            "predictions": logits.argmax(dim=1).tolist()}


def sample_indices(seed: int, steps: int, count: int) -> list[list[int]]:
    rng = random.Random(seed ^ 0x9A712)
    return [[rng.randrange(count) for _ in range(16)] for _ in range(steps)]


def check_gradients(views: dict[str, torch.Tensor]) -> dict[str, float]:
    """Numerical derivative of the dense path, and hard-forward/surrogate identities."""
    small = {key: value[:3] for key, value in views.items()}
    model = CellModel(812, "dense").double()
    small = {key: value.double() if value.is_floating_point() else value for key, value in small.items()}
    loss = F.cross_entropy(model(features(small)), small["targets"])
    loss.backward()
    maximum = 0.0
    for name, parameter in model.named_parameters():
        for index in sorted({0, parameter.numel() // 2, parameter.numel() - 1}):
            exact = parameter.grad.flatten()[index].item()
            original = parameter.detach().flatten()[index].item()
            with torch.no_grad():
                parameter.flatten()[index] = original + 1e-5
                plus = F.cross_entropy(model(features(small)), small["targets"]).item()
                parameter.flatten()[index] = original - 1e-5
                minus = F.cross_entropy(model(features(small)), small["targets"]).item()
                parameter.flatten()[index] = original
            error = abs(exact - (plus - minus) / 2e-5)
            maximum = max(maximum, error)
            if error > 1e-7:
                raise ContractError(f"dense numerical gradient differs for {name}: {error}")
    model = CellModel(812, "selective")
    first = model({key: value[:3].float() if value.is_floating_point() else value[:3]
                   for key, value in features(views).items()})
    replica = CellModel.from_artifact(model.artifact(0))
    second = replica({key: value[:3] for key, value in features(views).items()})
    if not torch.equal(first, second):
        raise ContractError("parameter artifact round trip changed logits")
    return {"dense_maximum_gradient_error": maximum, "parameter_count": sum(p.numel() for p in model.parameters())}
