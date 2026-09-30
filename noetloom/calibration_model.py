"""Backend-independent dimensions, snapshot validation and scalar inference reference."""
from __future__ import annotations

import math

from .contracts import ContractError, fields, integer

ARMS = ("shared_rows", "transport", "bypass")


def shapes(arm: str) -> dict:
    if arm not in ARMS:
        raise ContractError("unknown calibration arm")
    if arm == "shared_rows":
        return {"encoder": [(8, 32, True), (32, 16, True)],
                "solver": [(16, 32, True), (32, 2, False)]}
    return {"encoder": [(64, 16, True), (16, 1024, False)],
            "solver": [(80 if arm == "bypass" else 16, 32, True), (32, 32, True), (32, 2, False)]}


def parameter_count(arm: str) -> int:
    return sum((i + 1) * o for layers in shapes(arm).values() for i, o, _ in layers)


def forward_ops(arm: str) -> int:
    dimensions = shapes(arm)
    cost = lambda group: sum(2 * i * o + o + (o if activation else 0) for i, o, activation in dimensions[group])
    return cost("solver") + (6 * cost("encoder") + 5 * 16 if arm == "shared_rows"
                              else cost("encoder") + 16 * (5 * 64 - 2) + 16 * 127)


def validate_snapshot(value: dict) -> None:
    fields(value, {"schema_version", "role", "arm", "seed", "step", "encoder", "solver"}, "calibration snapshot")
    if value["schema_version"] != "noetloom.calibration_parameters.v1" or value["role"] != "inference_parameters_only":
        raise ContractError("unsupported calibration parameter artifact")
    integer(value["seed"], "seed", 0, 2**32 - 1)
    integer(value["step"], "step", 0, 2048)
    for name, dimensions in shapes(value["arm"]).items():
        layers = value[name]
        if not isinstance(layers, list) or len(layers) != len(dimensions):
            raise ContractError("calibration layer count differs")
        for layer, (inputs, outputs, nonlinear) in zip(layers, dimensions):
            fields(layer, {"weights", "bias"}, "calibration layer")
            for key, count in (("weights", inputs * outputs), ("bias", outputs)):
                if (not isinstance(layer[key], list) or len(layer[key]) != count
                        or any(type(x) not in (int, float) or not math.isfinite(x) for x in layer[key])):
                    raise ContractError("calibration layer shape or finite-value contract differs")


def scalar_forward(snapshot: dict, values: list[float]) -> tuple[list[float], list[float]]:
    """Independent list/scalar implementation; no tensor backend, labels or task decoding."""
    validate_snapshot(snapshot)
    if len(values) != 64 or any(type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 2 for x in values):
        raise ContractError("calibration inference requires 64 bounded field values")
    dimensions = shapes(snapshot["arm"])

    def network(group: str, inputs: list[float]) -> list[float]:
        result = inputs
        for layer, (width, output, nonlinear) in zip(snapshot[group], dimensions[group]):
            result = [sum(w * x for w, x in zip(layer["weights"][i * width:(i + 1) * width], result))
                      + layer["bias"][i] for i in range(output)]
            if nonlinear:
                result = list(map(math.tanh, result))
        return result

    if snapshot["arm"] == "shared_rows":
        encoded = [network("encoder", values[i * 8:(i + 1) * 8]) for i in range(6)]
        intermediate = [sum(row[i] for row in encoded) for i in range(16)]
    else:
        raw = network("encoder", values)
        intermediate = []
        for row in range(16):
            logits = raw[row * 64:(row + 1) * 64]
            maximum = max(logits)
            weights = [math.exp(x - maximum) for x in logits]
            intermediate.append(sum(w * x for w, x in zip(weights, values)) / sum(weights))
        if snapshot["arm"] == "bypass":
            intermediate += values
    return network("solver", intermediate), intermediate
