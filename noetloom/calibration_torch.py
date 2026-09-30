"""Small learned calibration probes. No generator, scorer or latent metadata imports."""
from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F

from .calibration_model import parameter_count, shapes, validate_snapshot
from .contracts import ContractError


class Layer(nn.Module):
    def __init__(self, inputs: int, outputs: int, nonlinear: bool, generator: torch.Generator):
        super().__init__()
        self.weight = nn.Parameter(torch.randn(outputs, inputs, generator=generator) / math.sqrt(inputs))
        self.bias = nn.Parameter(torch.zeros(outputs))
        self.nonlinear = nonlinear

    def forward(self, values):
        result = F.linear(values, self.weight, self.bias)
        return result.tanh() if self.nonlinear else result


class Model(nn.Module):
    def __init__(self, arm: str, seed: int):
        super().__init__()
        self.arm, self.seed = arm, seed
        generator = torch.Generator(device="cpu").manual_seed(seed)
        for name, dimensions in shapes(arm).items():
            setattr(self, name, nn.ModuleList([Layer(i, o, activation, generator) for i, o, activation in dimensions]))
        if sum(p.numel() for p in self.parameters()) != parameter_count(arm):
            raise ContractError("calibration parameter count differs")

    def network(self, group, values):
        result = values
        for layer in getattr(self, group):
            result = layer(result)
        return result

    def construct(self, values):
        if self.arm == "shared_rows":
            return self.network("encoder", values[:, :48].reshape(-1, 6, 8)).sum(1)
        scores = self.network("encoder", values).reshape(-1, 16, 64)
        intermediate = torch.bmm(scores.softmax(-1), values.unsqueeze(2)).squeeze(2)
        return torch.cat((intermediate, values), 1) if self.arm == "bypass" else intermediate

    def forward(self, values):
        return self.network("solver", self.construct(values))

    def snapshot(self, step: int) -> dict:
        result = {"schema_version": "noetloom.calibration_parameters.v1", "role": "inference_parameters_only",
                  "arm": self.arm, "seed": self.seed, "step": step}
        for group in ("encoder", "solver"):
            result[group] = [{"weights": layer.weight.detach().flatten().tolist(), "bias": layer.bias.detach().tolist()}
                             for layer in getattr(self, group)]
        validate_snapshot(result)
        return result

    @classmethod
    def restore(cls, snapshot: dict):
        validate_snapshot(snapshot)
        result = cls(snapshot["arm"], snapshot["seed"])
        with torch.no_grad():
            for group in ("encoder", "solver"):
                for layer, raw in zip(getattr(result, group), snapshot[group]):
                    layer.weight.copy_(torch.tensor(raw["weights"]).reshape_as(layer.weight))
                    layer.bias.copy_(torch.tensor(raw["bias"]))
        return result
