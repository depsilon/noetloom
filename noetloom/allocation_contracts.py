"""Strict admission contract for the single registered EXP-0003 allocation protocol."""

from __future__ import annotations

import math
from typing import Any

from .contracts import ContractError, fields, identifier, integer, strings, text, validate_policy, version

_ARMS = ["adaptive", "top_one", "dense"]
_SEEDS = [1103, 2207, 3301, 4409, 5519]
_FAMILIES = ["base", "delay", "capacity", "interleaved"]
_SOURCE_REFS = ["R-ACT", "R-NTM", "R-ZOOLOGY"]
_MAX_WALL_SECONDS = 120
_MAX_OUTPUT_BYTES = 16 * 1024**2
_MAX_PRESENTATIONS = 10_000
_MAX_PEAK_RSS_BYTES = 2 * 1024**3


def _fixed_text(value: Any, expected: str, where: str) -> None:
    text(value, where)
    if value != expected:
        raise ContractError(f"{where} differs from registered EXP-0003")


def _fixed_integer(value: Any, expected: int, where: str) -> None:
    integer(value, where, expected, expected)


def _fixed_number(value: Any, expected: float, where: str) -> None:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ContractError(f"{where} must be a finite number")
    if value != expected:
        raise ContractError(f"{where} differs from registered EXP-0003")


def _fixed_number_list(value: Any, expected: list[float], where: str) -> None:
    if not isinstance(value, list) or len(value) != len(expected):
        raise ContractError(f"{where} must contain {len(expected)} registered values")
    for index, (item, expected_item) in enumerate(zip(value, expected)):
        _fixed_number(item, expected_item, f"{where}[{index}]")


def _fixed_strings(value: Any, expected: list[str], where: str) -> None:
    if strings(value, where) != expected:
        raise ContractError(f"{where} differs from registered EXP-0003")


def validate_allocation_protocol(protocol: dict[str, Any], policy: dict[str, Any]) -> None:
    """Validate the frozen EXP-0003 scientific instance and host resource ceilings."""
    validate_policy(policy)
    fields(protocol, {
        "schema_version", "id", "kind", "hypothesis_id", "source_refs", "design", "parents",
        "arms", "seeds", "data", "gate", "training", "preflight", "budget", "acceptance",
        "network_during_run", "external_pretrained_components", "teacher_assistance",
        "artifact_rights", "claim_boundary",
    }, "allocation protocol")
    version(protocol, "noetloom.allocation.v1")
    identifier(protocol["id"], r"EXP-\d{4}", "experiment id")
    _fixed_text(protocol["id"], "EXP-0003", "experiment id")
    _fixed_text(protocol["kind"], "learned_read_allocation", "kind")
    _fixed_text(protocol["hypothesis_id"], "H-002", "hypothesis_id")
    _fixed_strings(protocol["source_refs"], _SOURCE_REFS, "source_refs")
    for key, expected in (
        ("design", "experiments/EXP-0003/design.md"),
        ("parents", "experiments/EXP-0003/parents.json"),
        ("teacher_assistance", "No model-generated examples or labels; synthetic generator and own-trained parent parameters only. Development code assisted by Codex."),
        ("artifact_rights", "Generated synthetic data retained locally; source Apache-2.0; checkpoint redistribution/license undecided."),
        ("claim_boundary", "Two-stage compute-allocation component probe over five frozen own-trained readers; no final architecture, procedural reuse, novelty, general intelligence, or speed claim."),
    ):
        _fixed_text(protocol[key], expected, key)

    _fixed_strings(protocol["arms"], _ARMS, "arms")
    seeds = protocol["seeds"]
    if not isinstance(seeds, list) or not seeds:
        raise ContractError("seeds must be a nonempty list")
    for index, seed in enumerate(seeds):
        integer(seed, f"seeds[{index}]", 0, 2**32 - 1)
    if len(seeds) != len(set(seeds)) or seeds != _SEEDS:
        raise ContractError("seeds differ from registered EXP-0003")

    data = protocol["data"]
    fields(data, {"generator_seed", "excluded_generator_seed", "train_episodes", "validation_episodes",
                  "test_episodes_per_family", "development_episodes", "queries_per_episode", "test_families"}, "data")
    for key, expected in (("generator_seed", 981733), ("excluded_generator_seed", 872341),
                          ("train_episodes", 64), ("validation_episodes", 32),
                          ("test_episodes_per_family", 32), ("development_episodes", 8),
                          ("queries_per_episode", 8)):
        _fixed_integer(data[key], expected, f"data.{key}")
    _fixed_strings(data["test_families"], _FAMILIES, "data.test_families")

    gate = protocol["gate"]
    fields(gate, {"features", "trainable_scalars", "initialization_stddev", "initialization_seed_xor",
                  "initial_bias", "continue_score_threshold", "payload_penalty"}, "gate")
    for key, expected in (("features", 6), ("trainable_scalars", 7), ("initialization_seed_xor", 44259)):
        _fixed_integer(gate[key], expected, f"gate.{key}")
    for key, expected in (("initialization_stddev", 0.1), ("initial_bias", 0.0),
                          ("continue_score_threshold", 0.0), ("payload_penalty", 0.02)):
        _fixed_number(gate[key], expected, f"gate.{key}")

    training = protocol["training"]
    fields(training, {"backend", "version", "device", "dtype", "threads", "candidate_steps", "batch_size",
                      "learning_rate", "betas", "epsilon", "weight_decay", "gradient_clip",
                      "validation_fractions", "selection"}, "training")
    for key, expected in (("backend", "torch"), ("version", "2.14.0"), ("device", "cpu"),
                          ("dtype", "float32"), ("selection", "lowest_deterministic_validation_error_plus_payload_penalty_then_earliest")):
        _fixed_text(training[key], expected, f"training.{key}")
    _fixed_integer(training["threads"], 1, "training.threads")
    steps = training["candidate_steps"]
    if not isinstance(steps, list) or not steps:
        raise ContractError("training.candidate_steps must be a nonempty list")
    for i, step in enumerate(steps):
        integer(step, f"training.candidate_steps[{i}]")
    if steps != [128, 64]:
        raise ContractError("training.candidate_steps differ from registered EXP-0003")
    _fixed_integer(training["batch_size"], 8, "training.batch_size")
    _fixed_number(training["learning_rate"], 0.02, "training.learning_rate")
    _fixed_number_list(training["betas"], [0.9, 0.999], "training.betas")
    for key, expected in (("epsilon", 1e-8), ("weight_decay", 0.0), ("gradient_clip", 1.0)):
        _fixed_number(training[key], expected, f"training.{key}")
    _fixed_number_list(training["validation_fractions"], [0.25, 0.5, 1.0], "training.validation_fractions")

    preflight = protocol["preflight"]
    fields(preflight, {"warmup_steps", "timed_steps", "extrapolated_training_seconds", "max_wall_seconds", "max_output_bytes"}, "preflight")
    for key, expected in (("warmup_steps", 8), ("timed_steps", 16), ("extrapolated_training_seconds", 30)):
        _fixed_integer(preflight[key], expected, f"preflight.{key}")
    for key, policy_key, cap in (("max_wall_seconds", "max_wall_seconds", _MAX_WALL_SECONDS),
                                 ("max_output_bytes", "max_run_output_bytes", _MAX_OUTPUT_BYTES)):
        integer(preflight[key], f"preflight.{key}", 1, min(cap, policy[policy_key]))

    budget = protocol["budget"]
    fields(budget, {"max_wall_seconds_per_run", "max_output_bytes_per_run", "max_query_presentations_per_run",
                    "max_training_attempts", "max_peak_rss_bytes"}, "budget")
    integer(budget["max_wall_seconds_per_run"], "budget.max_wall_seconds_per_run", 1,
            min(_MAX_WALL_SECONDS, policy["max_wall_seconds"]))
    integer(budget["max_output_bytes_per_run"], "budget.max_output_bytes_per_run", 1,
            min(_MAX_OUTPUT_BYTES, policy["max_run_output_bytes"]))
    integer(budget["max_query_presentations_per_run"], "budget.max_query_presentations_per_run", 1, _MAX_PRESENTATIONS)
    _fixed_integer(budget["max_training_attempts"], 5, "budget.max_training_attempts")
    integer(budget["max_peak_rss_bytes"], "budget.max_peak_rss_bytes", 1, _MAX_PEAK_RSS_BYTES)

    acceptance = protocol["acceptance"]
    fields(acceptance, {"all_family_accuracy", "minimum_family_accuracy", "dense_difference_ci_low",
                        "minimum_family_dense_difference", "random_difference_ci_low", "max_payload_read_ratio",
                        "max_nominal_scalar_ratio", "minimum_continue_rate", "maximum_continue_rate", "interval"}, "acceptance")
    for key, expected in (("all_family_accuracy", 0.80), ("minimum_family_accuracy", 0.70),
                          ("dense_difference_ci_low", -0.02), ("minimum_family_dense_difference", -0.03),
                          ("random_difference_ci_low", 0.005), ("max_payload_read_ratio", 0.50),
                          ("max_nominal_scalar_ratio", 1.0), ("minimum_continue_rate", 0.05),
                          ("maximum_continue_rate", 0.95)):
        _fixed_number(acceptance[key], expected, f"acceptance.{key}")
    _fixed_text(acceptance["interval"], "paired_training_seed_t95_df4", "acceptance.interval")

    if protocol["network_during_run"] is not False:
        raise ContractError("network_during_run must be false")
    if protocol["external_pretrained_components"] != []:
        raise ContractError("external_pretrained_components must be empty")

    maximum_presentations = (
        2 * data["train_episodes"] * data["queries_per_episode"]
        + max(steps) * training["batch_size"]
        + 2 * data["validation_episodes"] * data["queries_per_episode"]
        + len(training["validation_fractions"]) * data["validation_episodes"] * data["queries_per_episode"]
        + 2 * len(_ARMS) * len(_FAMILIES) * data["test_episodes_per_family"] * data["queries_per_episode"]
        + 16
    )
    if maximum_presentations > _MAX_PRESENTATIONS:
        raise ContractError("derived query presentations exceed the registered maximum")
    if maximum_presentations > budget["max_query_presentations_per_run"]:
        raise ContractError("derived query presentations exceed the per-run budget")
    if maximum_presentations > policy["max_cases"]:
        raise ContractError("derived query presentations exceed resource policy max_cases")
    if 33 > policy["max_memory_slots"]:
        raise ContractError("memory slot requirement exceeds resource policy max_memory_slots")
