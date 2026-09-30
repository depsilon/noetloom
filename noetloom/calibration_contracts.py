"""Strict registration and gates for one bounded acquisition pilot."""
from __future__ import annotations

import hashlib
import math
import statistics

from .contracts import ContractError, canonical_bytes

# Pin the complete reviewed registration, including unknown-key refusal. A protocol
# amendment requires an explicit source/registration change and a retained decision.
REGISTRATION = "278a473f01cbbd94d4c239f9767c02b698cdabdf9a934b4146625d9ea73189f2"
CONFIRMATION_REGISTRATION = "be42124d6b3806419f8e75218cd4ce18d0ec9fd131f6abbb4a5eecb0240ab8e7"


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


def validate_confirmation(value: dict) -> None:
    if hashlib.sha256(canonical_bytes(value)).hexdigest() != CONFIRMATION_REGISTRATION:
        raise ContractError("confirmation differs from its frozen selection amendment")


def seed_interval(values: list[float]) -> dict:
    if len(values) != 5 or any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        raise ContractError("confirmation interval needs five finite training-seed values")
    mean = statistics.mean(values)
    margin = 2.7764451051977987 * statistics.stdev(values) / math.sqrt(5)
    return {"mean": mean, "low": mean - margin, "high": mean + margin, "unit": "training_seed", "n": 5}


def confirmation_decision(registration: dict, results: dict) -> dict:
    validate_confirmation(registration)
    if set(results) != set(registration["seeds"]) or any(
            not row["acquisition"] or row.get("trained") is None or row.get("untrained") is None
            or row.get("run_status") != "passed" or row.get("replay_status") != "passed"
            or any(row.get("outcomes", {}).get(key, {}).get("status") != "completed" for key in ("fitting", "verification", "resource"))
            for row in results.values()):
        return {"decision": "not_confirmed", "reason": "at least one frozen seed missing, failed or did not acquire; no replacement or final tuning"}
    surfaces = ("ranks", "sequence", "relations")
    families = ("identity", "row_permutation", "transpose")
    values = {family: [] for family in families}
    minima = {family: 1.0 for family in families}
    baseline = []
    for seed in registration["seeds"]:
        row = results[seed]
        for key in ("trained", "untrained"):
            expected = {family + "/" + surface for family in families for surface in surfaces}
            if set(row[key]) != expected or any(type(entry["correct"]) is not int or not 0 <= entry["correct"] <= 192
                                               or entry["total"] != 192 or entry["class_support"] != [96, 96]
                                               or entry["accuracy"] != entry["correct"] / 192 for entry in row[key].values()):
                raise ContractError("final scoring support differs from frozen confirmation")
        for family in families:
            accuracies = [row["trained"][family + "/" + surface]["accuracy"] for surface in surfaces]
            values[family].append(statistics.mean(accuracies))
            minima[family] = min(minima[family], *accuracies)
        baseline.append(statistics.mean(row["untrained"]["identity/" + surface]["accuracy"] for surface in surfaces))
    difference = seed_interval([a - b for a, b in zip(values["identity"], baseline)])
    acquired = (statistics.mean(values["identity"]) >= registration["acquisition"]["mean_final_base_accuracy"]
                and minima["identity"] >= registration["acquisition"]["minimum_final_seed_format_accuracy"]
                and difference["low"] >= registration["acquisition"]["trained_minus_untrained_base_ci_low"])
    transfer = {}
    for family in families[1:]:
        change = seed_interval([a - b for a, b in zip(values[family], values["identity"])])
        retained = (statistics.mean(values[family]) >= registration["transfer"]["mean_accuracy"]
                    and minima[family] >= registration["transfer"]["minimum_seed_format_accuracy"]
                    and change["low"] >= registration["transfer"]["paired_change_from_base_ci_low"])
        transfer[family] = {"retained": bool(acquired and retained), "accuracy": seed_interval(values[family]),
                            "minimum_seed_format_accuracy": minima[family], "change_from_identity": change}
    return {"decision": "competent_baseline_confirmed" if acquired else "not_confirmed", "base": seed_interval(values["identity"]),
            "minimum_base_seed_format_accuracy": minima["identity"], "untrained_base": seed_interval(baseline),
            "trained_minus_untrained": difference, "transfer": transfer,
            "scope": "one fixed synthetic partition; seed variability only, no architecture or population-generalization claim"}
