"""EXP-0010 observation views over the existing non-final coordinate data."""
from __future__ import annotations

import math
import struct
from typing import Any

from . import state_rep_data as source
from .contracts import ContractError
from .input_audit import audit_inputs, require_informative_inputs

_VIEWS = {"old", "shift", "remix"}
_WIDTH = 10


def _finite_vector(vector: Any, where: str) -> list[float]:
    if not isinstance(vector, (list, tuple)) or len(vector) != _WIDTH:
        raise ContractError(f"{where} must be a ten-coordinate vector")
    if any(type(value) not in (int, float) for value in vector):
        raise ContractError(f"{where} must contain finite numeric coordinates")
    try:
        values = [float(value) for value in vector]
    except (OverflowError, ValueError) as exc:
        raise ContractError(f"{where} must contain finite numeric coordinates") from exc
    if any(not math.isfinite(value) for value in values):
        raise ContractError(f"{where} must contain finite numeric coordinates")
    return values


def _float32_bytes(vector: Any, where: str = "vector") -> bytes:
    values = _finite_vector(vector, where)
    try:
        packed = struct.pack("<10f", *values)
    except (OverflowError, struct.error) as exc:
        raise ContractError(f"{where} is outside finite float32 range") from exc
    if any(not math.isfinite(value) for value in struct.unpack("<10f", packed)):
        raise ContractError(f"{where} is outside finite float32 range")
    return packed


def _float32_values(vector: Any, where: str = "vector") -> list[float]:
    return list(struct.unpack("<10f", _float32_bytes(vector, where)))


def signature(row: dict) -> tuple[bytes, tuple[int, ...]]:
    """Return the model-visible float32 initial vector and ordered action word."""
    if not isinstance(row, dict):
        raise ContractError("signature row must be an object")
    actions = row.get("actions")
    if (not isinstance(actions, (list, tuple)) or not actions
            or any(type(action) is not int or not 0 <= action < 4 for action in actions)):
        raise ContractError("signature actions must be a nonempty action list")
    return _float32_bytes(row.get("initial"), "initial"), tuple(actions)


def _change(protocol: dict) -> tuple[list[float], list[list[float]]]:
    try:
        change = protocol["observation_change"]
        offset = _finite_vector(change["shift"], "registered shift")
        matrix_value = change["remix_matrix"]
    except (KeyError, TypeError) as exc:
        raise ContractError("protocol lacks the registered observation change") from exc
    if not isinstance(matrix_value, list) or len(matrix_value) != _WIDTH:
        raise ContractError("registered remix matrix must be 10 x 10")
    matrix = [_finite_vector(row, "registered remix row") for row in matrix_value]
    return offset, matrix


def transform(protocol: dict, observation: str, vector: list[float], work=None) -> list[float]:
    """Map an old nonlinear observation to old, shifted, or remixed coordinates."""
    if not isinstance(observation, str) or observation not in _VIEWS:
        raise ContractError("unknown representation-bridge observation view")
    values = _finite_vector(vector, "observation")
    if observation == "old":
        return values
    offset, matrix = _change(protocol)
    if observation == "shift":
        result = [value + bias for value, bias in zip(values, offset)]
        if work is not None:
            work.add("view_vectors", 1)
            work.add("view_add", _WIDTH)
    else:
        result = [math.fsum(matrix[row][column] * values[column] for column in range(_WIDTH)) + offset[row]
                  for row in range(_WIDTH)]
        if work is not None:
            work.add("view_vectors", 1)
            work.add("view_multiply", _WIDTH * _WIDTH)
            work.add("view_add", _WIDTH * _WIDTH)
    if any(not math.isfinite(value) for value in result):
        raise ContractError("transformed observation is nonfinite")
    return result


def _row(protocol: dict, observation: str, row: dict, work=None) -> dict:
    return {
        "initial": transform(protocol, observation, row["initial"], work),
        "actions": list(row["actions"]),
        "targets": [transform(protocol, observation, target, work) for target in row["targets"]],
        "family": row["family"],
    }


def generate(protocol: dict, observation: str, stage: str, work=None) -> dict[str, list[dict]]:
    """Return train/validation rows with only the selected observation view."""
    if not isinstance(observation, str) or observation not in _VIEWS:
        raise ContractError("unknown representation-bridge observation view")
    raw = source.generate(protocol, "nonlinear", stage)
    return {split: [_row(protocol, observation, row, work) for row in rows]
            for split, rows in raw.items()}


def development(protocol: dict, observation: str, work=None) -> list[dict]:
    if not isinstance(observation, str) or observation not in _VIEWS:
        raise ContractError("unknown representation-bridge observation view")
    return [_row(protocol, observation, row, work)
            for row in source.development(protocol, "nonlinear")]


def continuations(protocol: dict, observation: str, work=None) -> list[dict]:
    if not isinstance(observation, str) or observation not in _VIEWS:
        raise ContractError("unknown representation-bridge observation view")
    result = []
    for row in source.continuations(protocol, "nonlinear"):
        result.append({
            "history_a": _row(protocol, observation, row["history_a"], work),
            "history_b": _row(protocol, observation, row["history_b"], work),
            "current": transform(protocol, observation, row["current"], work),
            "suffix": list(row["suffix"]),
            "targets": [transform(protocol, observation, target, work) for target in row["targets"]],
            "family": row["family"],
        })
    return result


def _prefixes(rows: list[dict]) -> list[dict]:
    prefixes = []
    for row in rows:
        for index, target in enumerate(row["targets"]):
            prefixes.append({"initial": row["initial"], "actions": row["actions"][:index + 1],
                             "expected": _float32_values(target, "target")})
    return prefixes


def _continuation_prefixes(rows: list[dict]) -> list[dict]:
    result = []
    for pair in rows:
        result.extend(_prefixes((pair["history_a"], pair["history_b"])))
        result.extend(_prefixes(({"initial": pair["current"], "actions": pair["suffix"],
                                  "targets": pair["targets"]},)))
    return result


def _state_ids(protocol: dict) -> set[int]:
    config = protocol["data"]
    raw = source.acquisition_raw(protocol, "mixed")
    raw["development"] = source.development_raw(protocol)
    states: set[int] = set()
    for rows in raw.values():
        for initial, actions, _family in rows:
            states.update(source.path(config, initial, actions))
    for pair in source.continuation_raw(protocol):
        for start, actions in (pair["history_a"], pair["history_b"]):
            states.update(source.path(config, start, actions))
        states.update(source.path(config, pair["state"], pair["suffix"]))
    return states


def _geometry(protocol: dict) -> dict:
    offset, matrix = _change(protocol)
    if not any(value != 0 for value in offset):
        raise ContractError("registered observation shift must be nonzero")
    max_error = 0.0
    for row in range(_WIDTH):
        for column in range(_WIDTH):
            product = math.fsum(matrix[index][row] * matrix[index][column] for index in range(_WIDTH))
            max_error = max(max_error, abs(product - (1.0 if row == column else 0.0)))
    if max_error > 1e-10:
        raise ContractError("registered remix matrix is not orthogonal")
    offset_l2 = math.hypot(*offset)
    if not math.isfinite(offset_l2) or offset_l2 == 0:
        raise ContractError("registered observation shift must have a finite nonzero norm")
    return {"offset_l2": offset_l2,
            "max_orthogonality_error": max_error}


def _training_overlap(left: list[dict], right: list[dict]) -> dict[str, int]:
    from collections import Counter

    left_counts = Counter(signature(row) for row in _prefixes(left))
    right_counts = Counter(signature(row) for row in _prefixes(right))
    shared = left_counts.keys() & right_counts.keys()
    return {"distinct_signatures": len(shared),
            "old_cases": sum(left_counts[key] for key in shared),
            "new_cases": sum(right_counts[key] for key in shared)}


def audit(protocol: dict, work=None) -> dict:
    """Check registered transforms, actual float32 prefixes and admitted-state injectivity."""
    old_partition = source.audit(protocol, "nonlinear")
    _geometry_report = _geometry(protocol)
    old_data = generate(protocol, "old", "mixed", work)
    old_development = development(protocol, "old", work)
    old_continuations = continuations(protocol, "old", work)
    admitted_states = _state_ids(protocol)
    if not admitted_states:
        raise ContractError("representation audit has no admitted non-final states")

    reports: dict[str, dict] = {}
    rendered_training = {"old": old_data["training"]}
    observed_states = sorted(admitted_states)
    for view in ("old", "shift", "remix"):
        if view == "old":
            rendered = old_data
            dev_rows, pairs = old_development, old_continuations
        else:
            rendered = generate(protocol, view, "mixed", work)
            dev_rows = development(protocol, view, work)
            pairs = continuations(protocol, view, work)
            rendered_training[view] = rendered["training"]
        groups = {
            "training": _prefixes(rendered["training"]),
            "validation": _prefixes(rendered["validation"]),
            "development": _prefixes(dev_rows) + _continuation_prefixes(pairs),
        }
        input_report = audit_inputs(groups, signature)
        require_informative_inputs(input_report,
                                   disjoint_pairs=("training/validation", "training/development",
                                                   "validation/development"))
        vector_signatures = {_float32_bytes(transform(protocol, view,
                                                       source.observe(protocol["data"], state, "nonlinear"), work),
                                             "admitted observation")
                             for state in observed_states}
        injectivity = {"states": len(observed_states), "float32_vectors": len(vector_signatures),
                       "injective": len(vector_signatures) == len(observed_states)}
        if not injectivity["injective"]:
            raise ContractError(f"{view} view merges admitted states after float32 conversion")
        reports[view] = {
            "prefix_input_audit": input_report,
            "admitted_state_injectivity": injectivity,
        }

    for view in ("shift", "remix"):
        reports[view]["old_new_training_signature_overlap"] = _training_overlap(
            old_data["training"], rendered_training[view])
    return {"old_partition_audit": old_partition,
            "transform_geometry": _geometry_report,
            "views": reports,
            "scope": "Finite float32 observations and prefixes from training, validation, development and continuation inputs; no final observations rendered."}
