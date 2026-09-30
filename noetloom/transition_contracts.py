"""Admission and checkpoint rules for the bounded transition experiment."""
from __future__ import annotations

import hashlib
import math

from .contracts import ContractError, canonical_bytes

REGISTRATION = "1587227774be42c71dfbb176b4f9132286593c02491e466af1ce5e1e66b9c15d"


def validate_protocol(protocol: dict, policy: dict) -> None:
    if hashlib.sha256(canonical_bytes(protocol)).hexdigest() != REGISTRATION:
        raise ContractError("EXP-0006 differs from its reviewed executable registration")
    if policy["profile"] != protocol["resource_profile"]:
        raise ContractError("transition experiment requires local-calibration admission")
    for key, limit in (("max_wall_seconds_per_run", "max_wall_seconds"),
                       ("max_output_bytes_per_run", "max_run_output_bytes"),
                       ("max_case_presentations_per_run", "max_cases")):
        if protocol["budget"][key] > policy[limit]:
            raise ContractError("transition protocol exceeds resource profile")


def acquisition_gate(stage: str, measurement: dict, protocol: dict) -> dict:
    gates, checks = protocol["gates"], {}
    for group in ("training",) if stage == "tiny" else ("training", "validation"):
        scores = measurement[group]["scored"]
        expected = {"all", *("action/" + str(action) for action in range(4)),
                    *("length/" + str(length) for length in ((1, 2, 3) if stage == "mixed" else (1,)))}
        if not expected <= scores.keys():
            return {"passed": False, "reason": "missing required acquisition slices", "checks": {}}
        for key in sorted(expected):
            item = scores[key]
            checks[group + "/" + key] = bool(item["cases"] > 0 and item["changed_bits"] > 0
                and item["exact_accuracy"] >= gates[stage + "_" + group + "_exact"]
                and item["changed_bit_accuracy"] is not None
                and item["changed_bit_accuracy"] >= gates["changed_bit_accuracy"])
    return {"passed": all(checks.values()), "checks": checks}


def select_measurement(stage: str, measurements: list[dict], protocol: dict) -> tuple[int, dict]:
    objective = "training" if stage == "tiny" else "validation"
    candidates = [i for i, row in enumerate(measurements) if acquisition_gate(stage, row, protocol)["passed"]]
    for row in measurements:
        if not math.isfinite(row[objective]["loss"]):
            raise ContractError("nonfinite checkpoint selection loss")
    index = min(candidates or range(len(measurements)), key=lambda i: (measurements[i][objective]["loss"], measurements[i]["step"]))
    return index, acquisition_gate(stage, measurements[index], protocol)
