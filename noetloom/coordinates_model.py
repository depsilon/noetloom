"""Independent scalar equations for coordinate representation candidates."""
from __future__ import annotations

import math
from typing import Any

from . import state_rep_model as _legacy
from .contracts import ContractError

_SCHEMA = "noetloom.coordinates_parameters.v1"
_ARMS = {"latent", "direct", "reversible"}
_COUPLING = {
    "coupling_first_weight": (4, 30, 5), "coupling_first_bias": (4, 30),
    "coupling_last_weight": (4, 5, 30), "coupling_last_bias": (4, 5),
}
_SHAPES = {
    "latent": dict(_legacy.shapes("latent")),
    "direct": dict(_legacy.shapes("direct")),
    "reversible": {**_COUPLING, "transition_weight": (4, 10, 10),
                   "transition_bias": (4, 10)},
}
_COUNTS = {"latent": 1804, "direct": 5416, "reversible": 1780}


def shapes(arm: str) -> dict[str, tuple[int, ...]]:
    if not isinstance(arm, str) or arm not in _ARMS:
        raise ContractError("arm must be 'latent', 'direct' or 'reversible'")
    return dict(_SHAPES[arm])


def parameter_count(arm: str) -> int:
    shapes(arm)
    return _COUNTS[arm]


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    if not isinstance(snapshot, dict):
        raise ContractError("snapshot must be an object")
    if set(snapshot) != {"schema_version", "arm", "seed", "step", "tensors"}:
        raise ContractError("snapshot has missing or unknown fields")
    if snapshot["schema_version"] != _SCHEMA:
        raise ContractError(f"snapshot.schema_version must equal {_SCHEMA!r}")
    arm = snapshot["arm"]
    if not isinstance(arm, str) or arm not in _ARMS:
        raise ContractError("snapshot.arm must be 'latent', 'direct' or 'reversible'")
    if type(snapshot["seed"]) is not int or not 0 <= snapshot["seed"] <= 2**31 - 1:
        raise ContractError("snapshot.seed must be an integer in [0, 2147483647]")
    if type(snapshot["step"]) is not int or not 0 <= snapshot["step"] <= 8192:
        raise ContractError("snapshot.step must be an integer in [0, 8192]")
    tensors = snapshot["tensors"]
    expected = _SHAPES[arm]
    if not isinstance(tensors, dict) or tensors.keys() != expected.keys():
        raise ContractError(f"snapshot.tensors must contain exactly {sorted(expected)}")
    for name, shape in expected.items():
        _legacy._validate_tensor(tensors[name], shape, f"snapshot.tensors.{name}")


def initial_state(snapshot: dict[str, Any], observation: list[float]) -> list[float]:
    validate_snapshot(snapshot)
    values = _legacy._vector(observation, 10, "observation")
    if snapshot["arm"] == "reversible":
        return _coupling(snapshot["tensors"], values, inverse=False)
    return _legacy._initial_state(snapshot, values)


def advance(snapshot: dict[str, Any], state: list[float], action: int
            ) -> tuple[list[float], list[float]]:
    validate_snapshot(snapshot)
    values = _legacy._vector(state, 10, "state")
    action = _legacy._action(action)
    if snapshot["arm"] != "reversible":
        return _legacy._advance(snapshot, values, action)
    tensors = snapshot["tensors"]
    next_state = _legacy._affine(tensors["transition_weight"][action],
                                 tensors["transition_bias"][action], values)
    return _coupling(tensors, next_state, inverse=True), next_state


def scalar_forward(snapshot: dict[str, Any], initial: list[float], actions: list[int]
                   ) -> tuple[list[list[float]], list[list[float]]]:
    validate_snapshot(snapshot)
    observation = _legacy._vector(initial, 10, "initial")
    if not isinstance(actions, (list, tuple)):
        raise ContractError("actions must be a list or tuple")
    state = initial_state(snapshot, observation)
    outputs, states = [], []
    for action in actions:
        output, state = advance(snapshot, state, action)
        outputs.append(output)
        states.append(state)
    return outputs, states


def forward_ops(arm: str, steps: int) -> dict[str, int]:
    shapes(arm)
    if type(steps) is not int or steps < 0:
        raise ContractError("steps must be a nonnegative integer")
    if arm == "reversible":
        return {"multiply": 1200 + 1300 * steps, "add": 1220 + 1320 * steps,
                "tanh": 120 * (1 + steps)}
    return _legacy.forward_ops(arm, steps)


def _coupling(tensors: dict[str, Any], values: list[float], *, inverse: bool) -> list[float]:
    result = list(values)
    order = range(3, -1, -1) if inverse else range(4)
    for layer in order:
        source_indices = [0, 2, 4, 6, 8] if layer % 2 == 0 else [1, 3, 5, 7, 9]
        target_indices = [1, 3, 5, 7, 9] if layer % 2 == 0 else [0, 2, 4, 6, 8]
        source = [result[index] for index in source_indices]
        hidden = _legacy._affine(tensors["coupling_first_weight"][layer],
                                 tensors["coupling_first_bias"][layer], source)
        activated = [math.tanh(value) for value in hidden]
        update = _legacy._affine(tensors["coupling_last_weight"][layer],
                                 tensors["coupling_last_bias"][layer], activated)
        sign = -1.0 if inverse else 1.0
        for index, delta in zip(target_indices, update):
            result[index] += sign * delta
    return result
