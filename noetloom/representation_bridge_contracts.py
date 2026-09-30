"""Frozen experiment and acquisition selection for the EXP-0010 bridge study."""
from __future__ import annotations

import hashlib

from .contracts import ContractError, canonical_bytes
from .coordinates_model import validate_snapshot
from .state_rep_contracts import acquisition_gate, finite

PROTOCOL_SHA256 = "b01d2966cb08ce0d6c6d97151e67cd1972ae74a36ca6d1d686e76cf0bcee2fab"
ARMS = ("frozen_warm", "frozen_reset", "refit_warm", "refit_reset")


def validate_protocol(protocol: dict, policy: dict) -> None:
    if not isinstance(protocol, dict) or hashlib.sha256(canonical_bytes(protocol)).hexdigest() != PROTOCOL_SHA256:
        raise ContractError("frozen representation-bridge registration differs")
    budget = protocol["budget"]
    if (policy["profile"] != "local-calibration" or budget["max_wall_seconds_per_run"] > policy["max_wall_seconds"]
            or budget["max_output_bytes_per_run"] > policy["max_run_output_bytes"]
            or budget["max_presentations_per_run"] > policy["max_cases"]):
        raise ContractError("resource policy does not admit representation-bridge acquisition")


def parent_spec(protocol: dict, seed: int) -> dict:
    if type(seed) is not int:
        raise ContractError("bridge seed must identify a retained parent")
    matches = [parent for parent in protocol["parents"] if parent["seed"] == seed]
    if len(matches) != 1:
        raise ContractError("bridge seed has no unique registered parent")
    return matches[0]


def frozen(arm: str) -> bool:
    if arm not in ARMS:
        raise ContractError("unregistered bridge arm")
    return arm.startswith("frozen_")


def warm(arm: str) -> bool:
    frozen(arm)
    return arm.endswith("_warm")


def operation_digest(snapshot: dict) -> str:
    validate_snapshot(snapshot)
    if snapshot["arm"] != "reversible":
        raise ContractError("bridge requires the registered reversible model")
    return hashlib.sha256(canonical_bytes({name: value for name, value in snapshot["tensors"].items()
                                         if name.startswith("transition_")})).hexdigest()


def select_measurement(protocol: dict, stage: str, measurements: list[dict]) -> tuple[int, dict]:
    if not measurements:
        raise ContractError("no bridge acquisition measurements")
    gates = [acquisition_gate(protocol, stage, row) for row in measurements]
    acquired = [index for index, gate in enumerate(gates) if gate["passed"]]
    if acquired:
        selected = min(acquired, key=lambda index: measurements[index]["step"])
    else:
        selected = min(range(len(measurements)), key=lambda index: (
            finite(measurements[index]["validation"]["loss"], "selection loss"), measurements[index]["step"]))
    return selected, gates[selected]
