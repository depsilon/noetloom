"""Strict admission contract for the single registered EXP-0004 protocol."""

from __future__ import annotations

import math
from typing import Any

from .contracts import ContractError, fields, identifier, integer, strings, text, validate_policy, version

_ARMS = ["fixed_small", "fixed_large", "conditional", "static"]
_SEEDS = [6101, 6203, 6301, 6407, 6503]
_SOURCE_REFS = ["R-STN", "R-SLOT"]
_SURFACES = ["ranks", "sequence", "relations"]
_TEST_FAMILIES = ["base", "combination", "reflection", "joint"]
_MAX_WALL_SECONDS = 120
_MAX_OUTPUT_BYTES = 32 * 1024**2
_MAX_CASE_PRESENTATIONS = 10_000
_MAX_TRAINING_ATTEMPTS = 20
_MAX_PEAK_RSS_BYTES = 2 * 1024**3
_MAX_TRAINING_PROXY_OPS = 2_000_000_000
_MAX_FORWARD_SCALAR_OPS = 100_000
_MAX_PRESENTATIONS = 8560


def _fixed_text(value: Any, expected: str, where: str) -> None:
    text(value, where)
    if value != expected:
        raise ContractError(f"{where} differs from registered EXP-0004")


def _fixed_integer(value: Any, expected: int, where: str) -> None:
    integer(value, where, expected, expected)


def _fixed_number(value: Any, expected: float, where: str) -> None:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ContractError(f"{where} must be a finite number")
    if value != expected:
        raise ContractError(f"{where} differs from registered EXP-0004")


def _fixed_number_list(value: Any, expected: list[float], where: str) -> None:
    if not isinstance(value, list) or len(value) != len(expected):
        raise ContractError(f"{where} must contain {len(expected)} registered values")
    for index, (item, expected_item) in enumerate(zip(value, expected)):
        _fixed_number(item, expected_item, f"{where}[{index}]")


def _fixed_integer_list(value: Any, expected: list[int], where: str) -> None:
    if not isinstance(value, list) or len(value) != len(expected):
        raise ContractError(f"{where} must contain {len(expected)} registered values")
    for index, (item, expected_item) in enumerate(zip(value, expected)):
        _fixed_integer(item, expected_item, f"{where}[{index}]")


def _fixed_strings(value: Any, expected: list[str], where: str) -> None:
    if strings(value, where) != expected:
        raise ContractError(f"{where} differs from registered EXP-0004")


def _fixed_string_map(value: Any, expected: dict[str, list[int]], where: str) -> None:
    fields(value, set(expected), where)
    for key, values in expected.items():
        _fixed_integer_list(value[key], values, f"{where}.{key}")


def validate_representation_protocol(protocol: dict[str, Any], policy: dict[str, Any]) -> None:
    """Validate frozen EXP-0004 science and resource limits against the host policy."""
    validate_policy(policy)
    fields(protocol, {
        "schema_version", "id", "kind", "hypothesis_id", "source_refs", "design", "arms", "seeds",
        "data", "model", "training", "preflight", "budget", "acceptance", "network_during_run",
        "external_pretrained_components", "teacher_assistance", "artifact_rights", "claim_boundary",
    }, "representation protocol")
    version(protocol, "noetloom.representation.v1")
    identifier(protocol["id"], r"EXP-\d{4}", "experiment id")
    for key, expected in (
        ("id", "EXP-0004"), ("kind", "learned_problem_representation"), ("hypothesis_id", "H-011"),
        ("design", "experiments/EXP-0004/design.md"),
        ("teacher_assistance", "No model-generated examples, labels, or inherited parameters; synthetic generator only. Development code assisted by Codex."),
        ("artifact_rights", "Generated synthetic data retained locally; source Apache-2.0; checkpoint redistribution/license undecided."),
        ("claim_boundary", "Input-dependent organization within a supplied numeric field and latent width; no unrestricted representation discovery, procedural reuse, novelty, general intelligence, or speed claim."),
    ):
        _fixed_text(protocol[key], expected, key)
    _fixed_strings(protocol["source_refs"], _SOURCE_REFS, "source_refs")
    _fixed_strings(protocol["arms"], _ARMS, "arms")
    seeds = protocol["seeds"]
    if not isinstance(seeds, list) or not seeds:
        raise ContractError("seeds must be a nonempty list")
    for index, seed in enumerate(seeds):
        integer(seed, f"seeds[{index}]", 0, 2**32 - 1)
    if len(seeds) != len(set(seeds)) or seeds != _SEEDS:
        raise ContractError("seeds differ from registered EXP-0004")

    data = protocol["data"]
    fields(data, {"generator_seed", "entities", "field_side", "training_cases", "validation_cases",
                  "development_cases", "test_cases_per_family", "diagnostic_problems", "surfaces",
                  "test_families", "seen_rotations", "heldout_rotations", "rank_centers", "rank_jitter"}, "data")
    for key, expected in (("generator_seed", 731991), ("entities", 5), ("field_side", 8),
                          ("training_cases", 768), ("validation_cases", 96), ("development_cases", 32),
                          ("test_cases_per_family", 96), ("diagnostic_problems", 96)):
        _fixed_integer(data[key], expected, f"data.{key}")
    _fixed_strings(data["surfaces"], _SURFACES, "data.surfaces")
    _fixed_strings(data["test_families"], _TEST_FAMILIES, "data.test_families")
    _fixed_string_map(data["seen_rotations"], {"ranks": [0, 1, 2], "sequence": [1, 2, 3], "relations": [0, 2, 3]}, "data.seen_rotations")
    fields(data["heldout_rotations"], {"ranks", "sequence", "relations"}, "data.heldout_rotations")
    for key, expected in (("ranks", 3), ("sequence", 0), ("relations", 1)):
        _fixed_integer(data["heldout_rotations"][key], expected, f"data.heldout_rotations.{key}")
    _fixed_number_list(data["rank_centers"], [-0.8, -0.4, 0.0, 0.4, 0.8], "data.rank_centers")
    _fixed_number(data["rank_jitter"], 0.08, "data.rank_jitter")

    model = protocol["model"]
    fields(model, {"latent_scalars", "construction_hidden", "small_hidden", "large_hidden", "output_classes",
                   "activation", "initialization", "transport"}, "model")
    for key, expected in (("latent_scalars", 16), ("construction_hidden", 16), ("small_hidden", 32),
                          ("large_hidden", 160), ("output_classes", 2)):
        _fixed_integer(model[key], expected, f"model.{key}")
    for key, expected in (("activation", "tanh"),
                          ("initialization", "normal_inverse_sqrt_fan_in_zero_bias"),
                          ("transport", "row_softmax_dense_raw_field")):
        _fixed_text(model[key], expected, f"model.{key}")

    training = protocol["training"]
    fields(training, {"backend", "version", "device", "dtype", "threads", "candidate_steps", "batch_size",
                      "learning_rate", "betas", "epsilon", "weight_decay", "gradient_clip",
                      "validation_fractions", "selection", "minibatch_seed_xor"}, "training")
    for key, expected in (("backend", "torch"), ("version", "2.14.0"), ("device", "cpu"), ("dtype", "float32"),
                          ("selection", "lowest_validation_cross_entropy_then_earliest")):
        _fixed_text(training[key], expected, f"training.{key}")
    _fixed_integer(training["threads"], 1, "training.threads")
    _fixed_integer_list(training["candidate_steps"], [1024, 512], "training.candidate_steps")
    _fixed_integer(training["batch_size"], 6, "training.batch_size")
    _fixed_integer(training["minibatch_seed_xor"], 22109, "training.minibatch_seed_xor")
    for key, expected in (("learning_rate", 0.003), ("epsilon", 1e-8), ("weight_decay", 0.0), ("gradient_clip", 1.0)):
        _fixed_number(training[key], expected, f"training.{key}")
    _fixed_number_list(training["betas"], [0.9, 0.999], "training.betas")
    _fixed_number_list(training["validation_fractions"], [0.25, 0.5, 1.0], "training.validation_fractions")

    preflight = protocol["preflight"]
    fields(preflight, {"warmup_steps", "timed_steps", "extrapolated_training_seconds", "max_wall_seconds", "max_output_bytes"}, "preflight")
    for key, expected in (("warmup_steps", 8), ("timed_steps", 16), ("extrapolated_training_seconds", 60)):
        _fixed_integer(preflight[key], expected, f"preflight.{key}")
    integer(preflight["max_wall_seconds"], "preflight.max_wall_seconds", 1,
            min(_MAX_WALL_SECONDS, policy["max_wall_seconds"]))
    integer(preflight["max_output_bytes"], "preflight.max_output_bytes", 1,
            min(_MAX_OUTPUT_BYTES, policy["max_run_output_bytes"]))

    budget = protocol["budget"]
    fields(budget, {"max_wall_seconds_per_run", "max_output_bytes_per_run", "max_case_presentations_per_run",
                    "max_training_attempts", "max_peak_rss_bytes", "max_training_proxy_ops",
                    "max_forward_scalar_ops"}, "budget")
    integer(budget["max_wall_seconds_per_run"], "budget.max_wall_seconds_per_run", 1,
            min(_MAX_WALL_SECONDS, policy["max_wall_seconds"]))
    integer(budget["max_output_bytes_per_run"], "budget.max_output_bytes_per_run", 1,
            min(_MAX_OUTPUT_BYTES, policy["max_run_output_bytes"]))
    integer(budget["max_case_presentations_per_run"], "budget.max_case_presentations_per_run", 1,
            _MAX_CASE_PRESENTATIONS)
    integer(budget["max_training_attempts"], "budget.max_training_attempts", 1, _MAX_TRAINING_ATTEMPTS)
    integer(budget["max_peak_rss_bytes"], "budget.max_peak_rss_bytes", 1, _MAX_PEAK_RSS_BYTES)
    integer(budget["max_training_proxy_ops"], "budget.max_training_proxy_ops", 1, _MAX_TRAINING_PROXY_OPS)
    integer(budget["max_forward_scalar_ops"], "budget.max_forward_scalar_ops", 1, _MAX_FORWARD_SCALAR_OPS)

    acceptance = protocol["acceptance"]
    fields(acceptance, {"base_accuracy", "transfer_accuracy", "minimum_transfer_family_accuracy",
                        "minimum_seed_transfer_accuracy", "control_difference_ci_low",
                        "intervention_difference_ci_low", "cross_surface_agreement", "acquisition_floor",
                        "absolute_parity_tolerance", "interval"}, "acceptance")
    for key, expected in (("base_accuracy", 0.85), ("transfer_accuracy", 0.75),
                          ("minimum_transfer_family_accuracy", 0.70), ("minimum_seed_transfer_accuracy", 0.60),
                          ("control_difference_ci_low", 0.05), ("intervention_difference_ci_low", 0.03),
                          ("cross_surface_agreement", 0.80), ("acquisition_floor", 0.70),
                          ("absolute_parity_tolerance", 0.0002)):
        _fixed_number(acceptance[key], expected, f"acceptance.{key}")
    _fixed_text(acceptance["interval"], "paired_training_seed_t95_df4", "acceptance.interval")

    if protocol["network_during_run"] is not False:
        raise ContractError("network_during_run must be false")
    if protocol["external_pretrained_components"] != []:
        raise ContractError("external_pretrained_components must be empty")

    maximum_presentations = 1024 * 6 + 3 * 96 + 2 * 4 * 96 + 2 * 4 * 96 + 2 * 3 * 96 + 16
    if maximum_presentations != _MAX_PRESENTATIONS:
        raise ContractError("registered query presentation derivation is inconsistent")
    if maximum_presentations > budget["max_case_presentations_per_run"]:
        raise ContractError("derived case presentations exceed the per-run budget")
    if maximum_presentations > policy["max_cases"]:
        raise ContractError("derived case presentations exceed resource policy max_cases")
    if policy["max_memory_slots"] < 1:
        raise ContractError("representation intermediate requires one resident memory slot")
