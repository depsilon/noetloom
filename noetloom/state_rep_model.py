"""Independent scalar equations for the N-011 state representation candidates."""
from __future__ import annotations

import math
from typing import Any

from .contracts import ContractError

_SCHEMA = "noetloom.state_rep_parameters.v1"
_ARMS = {"latent", "consistent", "direct"}
_SHAPES = {
    "latent": {
        "encoder_first_weight": (32, 10), "encoder_first_bias": (32,),
        "encoder_last_weight": (10, 32), "encoder_last_bias": (10,),
        "decoder_first_weight": (32, 10), "decoder_first_bias": (32,),
        "decoder_last_weight": (10, 32), "decoder_last_bias": (10,),
        "transition_weight": (4, 10, 10), "transition_bias": (4, 10),
    },
    "consistent": {
        "encoder_first_weight": (32, 10), "encoder_first_bias": (32,),
        "encoder_last_weight": (10, 32), "encoder_last_bias": (10,),
        "decoder_first_weight": (32, 10), "decoder_first_bias": (32,),
        "decoder_last_weight": (10, 32), "decoder_last_bias": (10,),
        "transition_weight": (4, 10, 10), "transition_bias": (4, 10),
    },
    "direct": {
        "first_weight": (4, 64, 10), "first_bias": (4, 64),
        "last_weight": (4, 10, 64), "last_bias": (4, 10),
    },
}
_COUNTS = {"latent": 1804, "consistent": 1804, "direct": 5416}


def _fail(where: str, message: str) -> None:
    raise ContractError(f"{where} {message}")


def _number(value: Any, where: str) -> float:
    if type(value) not in (int, float):
        _fail(where, "must be a finite number")
    try:
        result = float(value)
    except OverflowError:
        _fail(where, "must be a finite number")
    if not math.isfinite(result):
        _fail(where, "must be a finite number")
    return result


def shapes(arm: str) -> dict[str, tuple[int, ...]]:
    """Return the exact tensor names and dimensions for an arm."""
    if not isinstance(arm, str) or arm not in _ARMS:
        _fail("arm", "must be 'latent', 'consistent' or 'direct'")
    return dict(_SHAPES[arm])


def parameter_count(arm: str) -> int:
    """Return the declared scalar parameter count for an arm."""
    if not isinstance(arm, str) or arm not in _COUNTS:
        _fail("arm", "must be 'latent', 'consistent' or 'direct'")
    return _COUNTS[arm]


def _validate_tensor(value: Any, shape: tuple[int, ...], where: str) -> None:
    if not isinstance(value, list):
        _fail(where, "must be a nested list")
    if len(value) != shape[0]:
        _fail(where, f"must have leading dimension {shape[0]}")
    if len(shape) == 1:
        for i, item in enumerate(value):
            _number(item, f"{where}[{i}]")
    else:
        for i, item in enumerate(value):
            _validate_tensor(item, shape[1:], f"{where}[{i}]")


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    """Check the exact versioned snapshot fields, dimensions and scalar values."""
    if not isinstance(snapshot, dict):
        _fail("snapshot", "must be an object")
    if set(snapshot) != {"schema_version", "arm", "seed", "step", "tensors"}:
        _fail("snapshot", "has missing or unknown fields")
    if snapshot.get("schema_version") != _SCHEMA:
        _fail("snapshot.schema_version", f"must equal {_SCHEMA!r}")
    arm = snapshot.get("arm")
    if not isinstance(arm, str) or arm not in _ARMS:
        _fail("snapshot.arm", "must be 'latent', 'consistent' or 'direct'")
    if type(snapshot.get("seed")) is not int or not 0 <= snapshot["seed"] <= 2**31 - 1:
        _fail("snapshot.seed", "must be an integer in [0, 2147483647]")
    if type(snapshot.get("step")) is not int or not 0 <= snapshot["step"] <= 4352:
        _fail("snapshot.step", "must be an integer in [0, 4352]")
    tensors = snapshot.get("tensors")
    expected = _SHAPES[arm]
    if not isinstance(tensors, dict) or tensors.keys() != expected.keys():
        _fail("snapshot.tensors", f"must contain exactly {sorted(expected)}")
    for name, shape in expected.items():
        _validate_tensor(tensors[name], shape, f"snapshot.tensors.{name}")


def _vector(values: Any, size: int, where: str) -> list[float]:
    if not isinstance(values, (list, tuple)) or len(values) != size:
        _fail(where, f"must contain exactly {size} values")
    return [_number(value, f"{where}[{index}]") for index, value in enumerate(values)]


def _action(action: Any) -> int:
    if type(action) is not int or not 0 <= action < 4:
        _fail("action", "must be an integer in [0, 3]")
    return action


def _dot(row: list[float], values: list[float]) -> float:
    return sum(weight * value for weight, value in zip(row, values))


def _affine(weight: list[list[float]], bias: list[float], values: list[float]) -> list[float]:
    return [_dot(row, values) + offset for row, offset in zip(weight, bias)]


def _residual(tensors: dict[str, Any], prefix: str, values: list[float]) -> list[float]:
    hidden = _affine(tensors[f"{prefix}_first_weight"], tensors[f"{prefix}_first_bias"], values)
    activated = [math.tanh(value) for value in hidden]
    residual = _affine(tensors[f"{prefix}_last_weight"], tensors[f"{prefix}_last_bias"], activated)
    return [value + update for value, update in zip(values, residual)]


def _initial_state(snapshot: dict[str, Any], observation: list[float]) -> list[float]:
    return observation if snapshot["arm"] == "direct" else _residual(snapshot["tensors"], "encoder", observation)


def initial_state(snapshot: dict[str, Any], observation: list[float]) -> list[float]:
    """Map a ten-dimensional observation to the arm's initial state."""
    validate_snapshot(snapshot)
    values = _vector(observation, 10, "observation")
    return _initial_state(snapshot, values)


def _advance(snapshot: dict[str, Any], state: list[float], action: int) -> tuple[list[float], list[float]]:
    tensors, arm = snapshot["tensors"], snapshot["arm"]
    if arm == "direct":
        hidden = _affine(tensors["first_weight"][action], tensors["first_bias"][action], state)
        activated = [math.tanh(value) for value in hidden]
        update = _affine(tensors["last_weight"][action], tensors["last_bias"][action], activated)
        next_state = [value + delta for value, delta in zip(state, update)]
        return next_state, next_state
    next_state = _affine(tensors["transition_weight"][action], tensors["transition_bias"][action], state)
    decoded = _residual(tensors, "decoder", next_state)
    return decoded, next_state


def advance(snapshot: dict[str, Any], state: list[float], action: int) -> tuple[list[float], list[float]]:
    """Advance one step and return (decoded observation, next native state)."""
    validate_snapshot(snapshot)
    current = _vector(state, 10, "state")
    return _advance(snapshot, current, _action(action))


def scalar_forward(snapshot: dict[str, Any], initial: list[float], actions: list[int]
                    ) -> tuple[list[list[float]], list[list[float]]]:
    """Run scalar equations, returning per-step decoded outputs and states."""
    validate_snapshot(snapshot)
    observation = _vector(initial, 10, "initial")
    if not isinstance(actions, (list, tuple)):
        _fail("actions", "must be a list or tuple")
    state = _initial_state(snapshot, observation)
    outputs: list[list[float]] = []
    states: list[list[float]] = []
    for raw_action in actions:
        decoded, state = _advance(snapshot, state, _action(raw_action))
        outputs.append(decoded)
        states.append(state)
    return outputs, states


def forward_ops(arm: str, steps: int) -> dict[str, int]:
    """Return dense multiply/add and tanh operation counts for the declared scope."""
    if not isinstance(arm, str) or arm not in _ARMS:
        _fail("arm", "must be 'latent', 'consistent' or 'direct'")
    if type(steps) is not int or steps < 0:
        _fail("steps", "must be a nonnegative integer")
    if arm == "direct":
        return {"multiply": 1280 * steps, "add": 1290 * steps, "tanh": 64 * steps}
    return {"multiply": 640 + 740 * steps, "add": 650 + 750 * steps, "tanh": 32 * (1 + steps)}
