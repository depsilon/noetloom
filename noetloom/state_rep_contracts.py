"""Frozen scientific and resource boundaries for the EXP-0007 development pilot."""
from __future__ import annotations

import hashlib
import math

from .contracts import ContractError, canonical_bytes

BLOCKS = {
    "data": "a8976b995538dd3c5d8f6abe9246ed294a6ad8a8b41a237fbfc33d9b6708e6ef",
    "model": "b00578789485c9a488aa811d512a686756abe1f4ac03b9d3da642dbfd4f7be4a",
    "training": "e1cfe60af1ad1896600a4262c85f0ad3b4e21ad6a6d19809f197e9f8464693fa",
    "acquisition": "0bb330d63fe971685db7a0315ea4748dbd67326c24ce0cd82bb490f3ba3401fb",
    "evaluation": "25374ff12c5321cb51c949854357ba091da842128b32f56d2b21f86b9dc96e67",
    "budget": "136a0694a78cb768d168fe26fe2e4f62362ecfd0ba11fbae5d4a929148f81b41",
}
ROOT_KEYS = {"schema_version", "id", "kind", "design", "source_refs", "role", "observations", "arms", "development_seeds", "conditions",
             "data", "model", "training", "acquisition", "evaluation", "budget", "verification", "prior_evidence",
             "network_during_run", "external_pretrained_components", "final_access", "stop_condition"}


def validate_protocol(protocol: dict, policy: dict) -> None:
    if not isinstance(protocol, dict) or set(protocol) != ROOT_KEYS:
        raise ContractError("state-representation registration fields differ")
    expected = {"schema_version": "noetloom.state_representation.v1", "id": "EXP-0007", "kind": "development_pilot",
                "design": "experiments/EXP-0007/design.md", "source_refs": ["R-KOOPMAN", "R-E2C"],
                "observations": ["aligned", "nonlinear"], "arms": ["latent", "consistent", "direct"],
                "development_seeds": [11003, 11009, 11027],
                "conditions": [{"name": "lr003", "rate": 0.003}, {"name": "lr010", "rate": 0.01}],
                "prior_evidence": "docs/evidence/N-011-diagnostics-2026-09-30.json",
                "network_during_run": False, "external_pretrained_components": [], "final_access": False}
    if any(canonical_bytes(protocol[key]) != canonical_bytes(value) for key, value in expected.items()):
        raise ContractError("state-representation identity or data boundary differs")
    for key, digest in BLOCKS.items():
        if hashlib.sha256(canonical_bytes(protocol[key])).hexdigest() != digest:
            raise ContractError(f"frozen state-representation {key} differs")
    for key in ("role", "verification", "stop_condition"):
        if not isinstance(protocol[key], str) or not protocol[key].strip():
            raise ContractError("state-representation scope is missing")
    budget, training = protocol["budget"], protocol["training"]
    if (policy["profile"] != "local-calibration" or budget["max_wall_seconds_per_run"] > policy["max_wall_seconds"]
            or budget["max_output_bytes_per_run"] > policy["max_run_output_bytes"]
            or budget["max_presentations_per_run"] > policy["max_cases"]
            or budget["max_updates_per_run"] != sum(training["steps"].values())
            or budget["max_fit_attempts"] != 2 * 3 * 3 * 2):
        raise ContractError("state-representation resource policy does not admit this protocol")


def finite(value, name: str) -> float:
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ContractError(f"{name} must be finite numeric data")
    return float(value)


def acquisition_gate(protocol: dict, stage: str, measured: dict) -> dict:
    if stage not in protocol["training"]["steps"]:
        raise ContractError("unregistered acquisition stage")
    limits, checks = protocol["acquisition"], {}
    for split in ("training",) if stage == "tiny" else ("training", "validation"):
        result = measured[split]
        finite(result["loss"], "prediction MSE")
        groups = result["scored"]
        lengths = (1, 2, 3) if stage == "mixed" else (1,)
        required = ["all", *(f"length/{n}" for n in lengths), *(f"action/{n}" for n in range(4))]
        if any(key not in groups or type(groups[key]["cases"]) is not int or groups[key]["cases"] <= 0 for key in required):
            raise ContractError("acquisition lacks required nonempty action/length slices")
        floor = limits["tiny_training_all_prefix_accuracy"] if stage == "tiny" else limits[split + "_all_prefix_accuracy"]
        for key in required:
            accuracy = finite(groups[key]["all_prefix_exact_accuracy"], "complete-rollout accuracy")
            if not 0 <= accuracy <= 1:
                raise ContractError("acquisition accuracy outside [0,1]")
            target = floor if key == "all" or stage == "tiny" else limits["minimum_action_and_length_accuracy"]
            checks[split + "/" + key] = accuracy >= target
        reconstruction = finite(result["reconstruction"]["accuracy"], "reconstruction accuracy")
        if not 0 <= reconstruction <= 1:
            raise ContractError("reconstruction accuracy outside [0,1]")
        checks[split + "/reconstruction"] = reconstruction >= limits[split + "_reconstruction_accuracy"]
    return {"passed": all(checks.values()), "checks": checks}


def select_measurement(protocol: dict, stage: str, measurements: list[dict]) -> tuple[int, dict]:
    if not measurements:
        raise ContractError("no acquisition measurements")
    gates = [acquisition_gate(protocol, stage, measured) for measured in measurements]
    passed = [i for i, gate in enumerate(gates) if gate["passed"]]
    split = "training" if stage == "tiny" else "validation"
    index = min(passed or range(len(measurements)), key=lambda i: (finite(measurements[i][split]["loss"], "selection loss"), measurements[i]["step"]))
    return index, gates[index]
