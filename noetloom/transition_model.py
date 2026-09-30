"""Pure-Python scalar reference for the EXP-0006 transition candidates.

Operation counts are a scalar arithmetic proxy: every multiply and add is counted
separately, and each sigmoid/tanh invocation counts as one nonlinear call. They
are not wall-time, hardware, or memory-cost estimates.
"""
from __future__ import annotations

import math
from typing import Any

from .contracts import ContractError

_SCHEMA = "noetloom.transitions_parameters.v1"
_ARMS = {"shared_transition", "direct"}
_TENSOR_SHAPES = {
    "shared_transition": {"weight": (4, 8, 8), "bias": (4, 8)},
    "direct": {
        "encoder.weight": (64, 8), "encoder.bias": (64,),
        "cell.weight_ih": (192, 4), "cell.weight_hh": (192, 64),
        "cell.bias_ih": (192,), "cell.bias_hh": (192,),
        "decoder.weight": (8, 64), "decoder.bias": (8,),
    },
}


def _fail(where: str, message: str) -> None:
    raise ContractError(f"{where} {message}")


def _finite_number(value: Any, where: str) -> float:
    if type(value) not in (int, float):
        _fail(where, "must be a finite number")
    try:
        result = float(value)
    except OverflowError:
        _fail(where, "must be a finite number")
    if not math.isfinite(result):
        _fail(where, "must be a finite number")
    return result


def _validate_tensor(value: Any, shape: tuple[int, ...], where: str) -> None:
    if not isinstance(value, list):
        _fail(where, "must be a nested list")
    if len(shape) == 1:
        if len(value) != shape[0]:
            _fail(where, f"must have length {shape[0]}")
        for i, item in enumerate(value):
            _finite_number(item, f"{where}[{i}]")
        return
    if len(value) != shape[0]:
        _fail(where, f"must have length {shape[0]}")
    for i, item in enumerate(value):
        _validate_tensor(item, shape[1:], f"{where}[{i}]")


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    """Validate the exact versioned tensor snapshot contract."""
    if not isinstance(snapshot, dict):
        _fail("snapshot", "must be an object")
    if set(snapshot) != {"schema_version", "arm", "seed", "step", "tensors"}:
        _fail("snapshot", "has missing or unknown fields")
    if snapshot.get("schema_version") != _SCHEMA:
        _fail("snapshot.schema_version", f"must equal {_SCHEMA!r}")
    arm = snapshot.get("arm")
    if not isinstance(arm, str) or arm not in _ARMS:
        _fail("snapshot.arm", "must be 'shared_transition' or 'direct'")
    if type(snapshot.get("seed")) is not int or snapshot["seed"] < 0:
        _fail("snapshot.seed", "must be a nonnegative integer")
    if type(snapshot.get("step")) is not int or snapshot["step"] < 0:
        _fail("snapshot.step", "must be a nonnegative integer")
    tensors = snapshot.get("tensors")
    expected = _TENSOR_SHAPES[arm]
    if not isinstance(tensors, dict) or tensors.keys() != expected.keys():
        _fail("snapshot.tensors", f"must contain exactly {sorted(expected)}")
    for name, shape in expected.items():
        _validate_tensor(tensors[name], shape, f"snapshot.tensors.{name}")


def _vector(value: Any, size: int, where: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != size:
        _fail(where, f"must contain exactly {size} values")
    return [_finite_number(item, f"{where}[{i}]") for i, item in enumerate(value)]


def _dot(row: list[float], values: list[float]) -> float:
    return sum(weight * value for weight, value in zip(row, values))


def _sigmoid(value: float) -> float:
    # Stable for large finite logits.
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def _affine(weight: list[list[float]], bias: list[float], values: list[float]) -> list[float]:
    return [_dot(row, values) + offset for row, offset in zip(weight, bias)]


def initial_state(snapshot: dict[str, Any], initial: list[float]) -> list[float]:
    """Return native initial state: input bits for shared, encoded hidden state for direct."""
    validate_snapshot(snapshot)
    bits = _vector(initial, 8, "initial")
    if any(bit not in (0.0, 1.0) for bit in bits):
        _fail("initial", "must contain only binary values")
    if snapshot["arm"] == "shared_transition":
        return bits
    tensors = snapshot["tensors"]
    encoded_input = [2.0 * bit - 1.0 for bit in bits]
    return [math.tanh(x) for x in _affine(
        tensors["encoder.weight"], tensors["encoder.bias"], encoded_input
    )]


def advance(snapshot: dict[str, Any], state: list[float], action: int) -> tuple[list[float], list[float]]:
    """Apply one action, returning (8 output logits, next native state)."""
    validate_snapshot(snapshot)
    if type(action) is not int or not 0 <= action < 4:
        _fail("action", "must be an integer in [0, 3]")
    arm = snapshot["arm"]
    size = 8 if arm == "shared_transition" else 64
    current = _vector(state, size, "state")
    tensors = snapshot["tensors"]
    if arm == "shared_transition":
        logits = _affine(tensors["weight"][action], tensors["bias"][action],
                         [2.0 * value - 1.0 for value in current])
        return logits, [_sigmoid(value) for value in logits]

    x = [0.0] * 4
    x[action] = 1.0
    input_affine = _affine(tensors["cell.weight_ih"], tensors["cell.bias_ih"], x)
    hidden_affine = _affine(tensors["cell.weight_hh"], tensors["cell.bias_hh"], current)
    r = [_sigmoid(input_affine[i] + hidden_affine[i]) for i in range(64)]
    z = [_sigmoid(input_affine[64 + i] + hidden_affine[64 + i]) for i in range(64)]
    # PyTorch GRUCell uses reset-after-hidden-affine placement: r * (W_hn h + b_hn).
    n = [math.tanh(input_affine[128 + i] + r[i] * hidden_affine[128 + i])
         for i in range(64)]
    next_state = [(1.0 - z[i]) * n[i] + z[i] * current[i] for i in range(64)]
    logits = _affine(tensors["decoder.weight"], tensors["decoder.bias"], next_state)
    return logits, next_state


def scalar_forward(snapshot: dict[str, Any], initial: list[float], actions: list[int]
                    ) -> tuple[list[list[float]], list[list[float]]]:
    """Roll out actions, returning per-step logits and states (initial state excluded)."""
    state = initial_state(snapshot, initial)
    if not isinstance(actions, (list, tuple)):
        _fail("actions", "must be a list or tuple")
    all_logits: list[list[float]] = []
    all_states: list[list[float]] = []
    for action in actions:
        logits, state = advance(snapshot, state, action)
        all_logits.append(logits)
        all_states.append(state)
    return all_logits, all_states


def parameter_count(arm: str) -> int:
    """Return trainable scalar count for the named arm."""
    if arm == "shared_transition":
        return 288
    if arm == "direct":
        return 14536
    _fail("arm", "must be 'shared_transition' or 'direct'")
    raise AssertionError("unreachable")


def forward_ops(arm: str, length: int) -> dict[str, int]:
    """Return scalar operation proxy; mul/add separate, nonlinear calls count as one."""
    if not isinstance(arm, str) or arm not in _ARMS:
        _fail("arm", "must be 'shared_transition' or 'direct'")
    if type(length) is not int or length < 0:
        _fail("length", "must be a nonnegative integer")
    if arm == "shared_transition":
        # Per transition: 16 operations for bipolar scaling, 64 multiplies,
        # 64 dot-product adds + 8 bias adds,
        # and 8 sigmoid calls. Initial state is a direct copy.
        return {"multiply": 72 * length, "add": 80 * length,
                "sigmoid": 8 * length, "tanh": 0}
    # Encoder: 512 multiply, 512 dot adds + 64 bias adds, 64 tanh.
    # GRU step: input affine 768 mul, 768 dot adds + 192 bias adds;
    # hidden affine 12,288 mul, 12,288 dot adds + 192 bias adds; gate sums,
    # reset multiplication, and interpolation: 64*3 + 64 + 64*3 adds/muls
    # respectively. Decoder: 512 mul, 512 dot adds + 8 bias adds.
    per_step_mul = 768 + 12288 + 64 + 64 + 64 + 512
    per_step_add = 768 + 192 + 12288 + 192 + 128 + 64 + 128 + 512 + 8
    return {"multiply": 8 + 512 + per_step_mul * length,
            "add": 8 + 512 + 64 + per_step_add * length,
            "sigmoid": 128 * length, "tanh": 64 + 64 * length}
