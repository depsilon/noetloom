"""Strict registration and gates for one bounded acquisition pilot."""
from __future__ import annotations

import hashlib

from .contracts import ContractError, canonical_bytes

# Pin the complete reviewed registration, including unknown-key refusal. A protocol
# amendment requires an explicit source/registration change and a retained decision.
REGISTRATION = "278a473f01cbbd94d4c239f9767c02b698cdabdf9a934b4146625d9ea73189f2"


def validate_calibration_protocol(protocol: dict, policy: dict) -> None:
    if hashlib.sha256(canonical_bytes(protocol)).hexdigest() != REGISTRATION:
        raise ContractError("EXP-0005 differs from its registered development protocol")
    if policy["profile"] != protocol["resource_profile"]:
        raise ContractError("calibration requires its explicitly admitted resource profile")
    budget = protocol["budget"]
    for field, policy_field in (("max_wall_seconds_per_run", "max_wall_seconds"),
                                ("max_output_bytes_per_run", "max_run_output_bytes"),
                                ("max_case_presentations_per_run", "max_cases")):
        if budget[field] > policy[policy_field]:
            raise ContractError("calibration resource policy is insufficient")


def acquisition_gate(stage: str, selected: dict, protocol: dict) -> dict:
    gates = protocol["gates"]
    train = selected["training"]["scored"]
    validation = selected["validation"]["scored"]
    expected = {"identity/" + surface for surface in (protocol["data"]["surfaces"] if stage == "mixed" else ["ranks"])}
    if set(train) != expected or (stage != "tiny" and set(validation) != expected):
        raise ContractError("stage metrics omit a required format")
    train_threshold = gates[{"tiny": "tiny_training_accuracy", "single": "single_training_accuracy",
                             "mixed": "mixed_training_accuracy_per_format"}[stage]]
    checks = {"training/" + name: row["accuracy"] >= train_threshold for name, row in train.items()}
    if stage != "tiny":
        threshold = gates["single_validation_accuracy" if stage == "single" else "mixed_validation_accuracy_per_format"]
        checks.update({"validation/" + name: row["accuracy"] >= threshold for name, row in validation.items()})
    return {"passed": bool(checks) and all(checks.values()) and selected["step"] > 0, "checks": checks}
