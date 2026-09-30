"""Optional gate training; frozen parent readers never receive gradient updates."""
from __future__ import annotations

import copy
import math
import random

import torch
from torch import nn
from torch.nn import functional as F

from .contracts import ContractError
from .learning_torch import CellModel, features


def branches(parent: CellModel, views: dict) -> dict:
    """Counterfactual acquisition work. Runtime sparseness is measured only in Rust."""
    if set(views) != {"query", "keys", "inputs", "ages", "mask"}:
        raise ContractError("branch inputs must contain observations only")
    with torch.no_grad():
        query = F.linear(views["query"], parent.query)
        keys = F.linear(views["keys"], parent.key)
        scores = (keys * query.unsqueeze(1)).sum(-1) / math.sqrt(8) + parent.age * views["ages"]
        scores = scores.masked_fill(~views["mask"], -1e9)
        scores = torch.cat((parent.null_score.expand(len(query), 1), scores), dim=1)
        weights = torch.softmax(scores, dim=1)
        top = scores.argmax(dim=1)
        values = torch.tanh(F.linear(views["inputs"], parent.encoder, parent.encoder_bias))
        payloads = torch.cat((parent.null_payload.expand(len(query), 1, 8), values), dim=1)
        first = payloads[torch.arange(len(query)), top]
        sparse = F.linear(first, parent.decoder, parent.decoder_bias)
        dense = F.linear((weights.unsqueeze(-1) * payloads).sum(1), parent.decoder, parent.decoder_bias)
        routing_top = weights.topk(2, dim=1).values
        output_top = torch.softmax(sparse, dim=1).topk(2, dim=1).values
        count = views["mask"].sum(1) + 1
        entropy = -(weights * weights.clamp_min(torch.finfo(weights.dtype).tiny).log()).sum(1)
        gate_features = torch.stack((routing_top[:, 0], routing_top[:, 0] - routing_top[:, 1],
                                     entropy / count.clamp_min(2).to(weights.dtype).log(),
                                     output_top[:, 0], output_top[:, 0] - output_top[:, 1],
                                     (count - 1).to(weights.dtype) / 32), dim=1)
    return {"features": gate_features, "top_one": sparse, "dense": dense, "count": count}


def prepare(parent: CellModel, views: dict) -> dict:
    result = branches(parent, features(views))
    result["sparse_error"] = (result["top_one"].argmax(1) != views["targets"]).float()
    result["dense_error"] = (result["dense"].argmax(1) != views["targets"]).float()
    return result


class Gate(nn.Module):
    def __init__(self, seed: int):
        super().__init__()
        generator = torch.Generator(device="cpu").manual_seed(seed ^ 0xACE3)
        self.weights = nn.Parameter(torch.randn(6, generator=generator) * 0.1)
        self.bias = nn.Parameter(torch.zeros(()))

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        if values.ndim != 2 or values.shape[1] != 6 or not torch.isfinite(values).all():
            raise ContractError("gate requires six finite observation features")
        return (values * self.weights).sum(1) + self.bias

    def artifact(self) -> dict:
        return {"weights": self.weights.detach().tolist(), "bias": self.bias.item()}

    @classmethod
    def from_artifact(cls, value: dict) -> "Gate":
        if set(value) != {"weights", "bias"} or len(value["weights"]) != 6:
            raise ContractError("invalid gate artifact")
        model = cls(0)
        with torch.no_grad():
            model.weights.copy_(torch.tensor(value["weights"]))
            model.bias.copy_(torch.tensor(value["bias"]))
        if not all(torch.isfinite(p).all() for p in model.parameters()):
            raise ContractError("non-finite gate artifact")
        return model


def objective(gate: Gate, prepared: dict) -> torch.Tensor:
    probability = gate(prepared["features"]).sigmoid()
    ratio = (1 + probability * (prepared["count"] - 1)) / prepared["count"]
    return ((1 - probability) * prepared["sparse_error"] + probability * prepared["dense_error"]
            + 0.02 * ratio).mean()


def optimizer(gate: Gate) -> torch.optim.Optimizer:
    return torch.optim.Adam(gate.parameters(), lr=0.02, betas=(0.9, 0.999), eps=1e-8,
                            weight_decay=0.0, foreach=False, fused=False)


def update(gate: Gate, opt: torch.optim.Optimizer, prepared: dict, indices: list[int]) -> float:
    subset = {name: value[indices] for name, value in prepared.items()}
    opt.zero_grad(set_to_none=True)
    loss = objective(gate, subset)
    if not torch.isfinite(loss):
        raise ContractError("non-finite gate loss")
    loss.backward()
    torch.nn.utils.clip_grad_norm_(gate.parameters(), 1.0, error_if_nonfinite=True)
    opt.step()
    return float(loss.detach())


def sample_indices(seed: int, steps: int, count: int) -> list[list[int]]:
    rng = random.Random(seed ^ 0x9A713)
    return [[rng.randrange(count) for _ in range(8)] for _ in range(steps)]


def infer(gate: Gate, prepared: dict) -> dict:
    if set(prepared) != {"features", "top_one", "dense", "count"}:
        raise ContractError("allocation inference requires observation branches without labels or errors")
    with torch.no_grad():
        scores = gate(prepared["features"])
        continuing = scores >= 0
        logits = torch.where(continuing.unsqueeze(-1), prepared["dense"], prepared["top_one"])
        reads = torch.where(continuing, prepared["count"], 1)
    return {"logits": logits.tolist(), "predictions": logits.argmax(1).tolist(),
            "gate_features": prepared["features"].tolist(), "gate_scores": scores.tolist(),
            "continued": continuing.tolist(),
            "payload_reads": reads.tolist()}


def evaluate(gate: Gate, prepared: dict) -> dict:
    result = infer(gate, {name: prepared[name] for name in ("features", "top_one", "dense", "count")})
    with torch.no_grad():
        continuing = torch.tensor(result["continued"])
        error = torch.where(continuing, prepared["dense_error"], prepared["sparse_error"])
        utility = (error + 0.02 * torch.tensor(result["payload_reads"]) / prepared["count"]).mean()
    return {**result, "validation_objective": float(utility)}


def parameters(parent: dict, arm: str, gate: dict | None = None) -> dict:
    result = copy.deepcopy(parent)
    if arm == "adaptive":
        if gate is None:
            raise ContractError("adaptive parameters need a gate")
        result.update(schema_version="noetloom.cell_parameters.v2", arm="adaptive", gate=gate)
    elif arm in {"top_one", "dense"}:
        result["arm"] = "selective" if arm == "top_one" else "dense"
    else:
        raise ContractError("unknown allocation policy")
    return result


def check_gradients(prepared: dict) -> dict:
    values = {name: value[:8].double() for name, value in prepared.items()}
    # Exercise both signs even when a development reader gives identical branch decisions.
    values["sparse_error"] = torch.tensor([0, 1, 1, 0, 1, 0, 0, 1], dtype=torch.float64)
    values["dense_error"] = 1 - values["sparse_error"]
    gate = Gate(812).double()
    objective(gate, values).backward()
    maximum = 0.0
    for parameter in gate.parameters():
        for index in range(parameter.numel()):
            exact = parameter.grad.flatten()[index].item()
            original = parameter.detach().flatten()[index].item()
            with torch.no_grad():
                parameter.flatten()[index] = original + 1e-5
                plus = objective(gate, values).item()
                parameter.flatten()[index] = original - 1e-5
                minus = objective(gate, values).item()
                parameter.flatten()[index] = original
            maximum = max(maximum, abs(exact - (plus - minus) / 2e-5))
    if maximum > 1e-7:
        raise ContractError("allocation numerical gradient mismatch")
    return {"maximum_absolute_error": maximum, "checked_scalars": 7}
