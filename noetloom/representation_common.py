"""Backend-independent EXP-0004 parameter, size and nominal-work contracts."""
from __future__ import annotations

import math

from .contracts import ContractError, fields, integer

ARMS = ("fixed_small", "fixed_large", "conditional", "static")


def shapes(arm: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    if arm not in ARMS:
        raise ContractError("unknown representation arm")
    hidden = 160 if arm == "fixed_large" else 32
    width = 64 if arm.startswith("fixed_") else 16
    return ([(64, 16), (16, 1024)] if arm == "conditional" else [],
            [(width, hidden), (hidden, hidden), (hidden, 2)])


def parameter_count(arm: str) -> int:
    construction, solver = shapes(arm)
    return sum((i + 1) * o for i, o in construction + solver) + (1024 if arm == "static" else 0)


def affine_ops(shape: tuple[int, int], nonlinear: bool) -> int:
    i, o = shape
    return 2 * i * o + o + (o if nonlinear else 0)


def construct_ops(arm: str) -> int:
    construction, _ = shapes(arm)
    if arm.startswith("fixed_"):
        return 0
    # Row softmax: n-1 comparisons, n subtractions/exp/divisions, n-1 additions.
    return (sum(affine_ops(shape, index == 0) for index, shape in enumerate(construction))
            + 16 * (5 * 64 - 2) + affine_ops((64, 16), False))


def solve_ops(arm: str) -> int:
    _, solver = shapes(arm)
    return sum(affine_ops(shape, index < 2) for index, shape in enumerate(solver))


def forward_ops(arm: str) -> int:
    return construct_ops(arm) + solve_ops(arm)


def training_proxy(arm: str, steps: int, batch_size: int = 6) -> int:
    return 3 * forward_ops(arm) * steps * batch_size + 10 * parameter_count(arm) * steps


def validate_parameters(value: dict) -> None:
    fields(value, {"schema_version", "arm", "seed", "step", "construction", "static_scores", "solver"},
           "representation parameters")
    if value["schema_version"] != "noetloom.representation_parameters.v1":
        raise ContractError("unsupported representation parameters")
    construction, solver = shapes(value["arm"])
    integer(value["seed"], "parameter seed", 0, 2**32 - 1)
    integer(value["step"], "parameter step", 0, 1024)

    def finite_vector(vector: list, size: int, where: str) -> None:
        if not isinstance(vector, list) or len(vector) != size:
            raise ContractError(f"{where} has wrong shape")
        if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 3.402823466e38 for v in vector):
            raise ContractError(f"{where} needs finite float32 parameters")

    for name, expected in (("construction", construction), ("solver", solver)):
        layers = value[name]
        if not isinstance(layers, list) or len(layers) != len(expected):
            raise ContractError(f"{name} differs from registered architecture")
        for index, (layer, (inputs, outputs)) in enumerate(zip(layers, expected)):
            fields(layer, {"input_dim", "output_dim", "weights", "bias", "activation"}, name)
            integer(layer["input_dim"], "input_dim", inputs, inputs)
            integer(layer["output_dim"], "output_dim", outputs, outputs)
            activation = "tanh" if index < len(expected) - 1 else "identity"
            if layer["activation"] != activation:
                raise ContractError("layer activation differs from registered architecture")
            finite_vector(layer["weights"], inputs * outputs, "weights")
            finite_vector(layer["bias"], outputs, "bias")
    finite_vector(value["static_scores"], 1024 if value["arm"] == "static" else 0, "static_scores")
