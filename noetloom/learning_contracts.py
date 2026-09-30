"""Strict admission contract for the single registered EXP-0002 learning protocol."""

from __future__ import annotations

import math
from typing import Any

from .contracts import (
    ContractError,
    fields,
    identifier,
    integer,
    strings,
    text,
    validate_policy,
    version,
)

_ARMS = ["selective", "dense", "frozen_routing", "no_history"]
_SEEDS = [1103, 2207, 3301, 4409, 5519]
_TEST_FAMILIES = ["base", "delay", "capacity", "composition"]
_SOURCE_REFS = ["R-NTM", "R-ZOOLOGY"]
_MAX_PRESENTATIONS = 10_000
_MAX_PEAK_RSS_BYTES = 2 * 1024**3
_MAX_WALL_SECONDS = 120
_MAX_OUTPUT_BYTES = 16 * 1024**2


def _fixed_text(value: Any, expected: str, where: str) -> None:
    text(value, where)
    if value != expected:
        raise ContractError(f"{where} differs from registered EXP-0002")


def _fixed_integer(value: Any, expected: int, where: str) -> None:
    integer(value, where, expected, expected)


def _fixed_number(value: Any, expected: float, where: str) -> None:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ContractError(f"{where} must be a finite number")
    if value != expected:
        raise ContractError(f"{where} differs from registered EXP-0002")


def _fixed_number_list(value: Any, expected: list[float], where: str) -> None:
    if not isinstance(value, list) or len(value) != len(expected):
        raise ContractError(f"{where} must contain {len(expected)} registered values")
    for index, (item, expected_item) in enumerate(zip(value, expected)):
        _fixed_number(item, expected_item, f"{where}[{index}]")


def _fixed_strings(value: Any, expected: list[str], where: str) -> None:
    actual = strings(value, where)
    if actual != expected:
        raise ContractError(f"{where} differs from registered EXP-0002")


def validate_learning_protocol(protocol: dict[str, Any], policy: dict[str, Any]) -> None:
    """Validate the frozen EXP-0002 contract against this host's resource ceilings."""
    validate_policy(policy)
    fields(
        protocol,
        {
            "schema_version", "id", "kind", "family", "hypothesis_id", "source_refs",
            "design", "arms", "seeds", "dimensions", "data", "training", "preflight",
            "budget", "acceptance", "network_during_run", "pretrained_components",
            "teacher_assistance", "artifact_rights", "claim_boundary",
        },
        "learning protocol",
    )
    version(protocol, "noetloom.learning.v1")
    identifier(protocol["id"], r"EXP-\d{4}", "experiment id")
    _fixed_text(protocol["id"], "EXP-0002", "experiment id")
    _fixed_text(protocol["kind"], "learned_state_selection", "kind")
    _fixed_text(protocol["family"], "event_cell_recall_v1", "family")
    _fixed_text(protocol["hypothesis_id"], "H-001", "hypothesis_id")
    _fixed_strings(protocol["source_refs"], _SOURCE_REFS, "source_refs")
    for key in ("design", "teacher_assistance", "artifact_rights", "claim_boundary"):
        text(protocol[key], key)

    _fixed_strings(protocol["arms"], _ARMS, "arms")
    if not isinstance(protocol["seeds"], list) or not protocol["seeds"]:
        raise ContractError("seeds must be a nonempty list")
    for index, seed in enumerate(protocol["seeds"]):
        integer(seed, f"seeds[{index}]", 0, 2**32 - 1)
    if len(protocol["seeds"]) != len(set(protocol["seeds"])):
        raise ContractError("seeds contain duplicates")
    if protocol["seeds"] != _SEEDS:
        raise ContractError("seeds differ from registered EXP-0002")

    dimensions = protocol["dimensions"]
    fields(dimensions, {"key", "latent", "values", "capacity"}, "dimensions")
    for key, expected in (("key", 16), ("latent", 8), ("values", 4), ("capacity", 32)):
        _fixed_integer(dimensions[key], expected, f"dimensions.{key}")
    if dimensions["capacity"] + 1 > policy["max_memory_slots"]:
        raise ContractError("capacity plus null cell exceeds resource policy max_memory_slots")

    data = protocol["data"]
    fields(
        data,
        {
            "generator_seed", "train_episodes", "validation_episodes",
            "test_episodes_per_family", "queries_per_episode", "test_families",
        },
        "data",
    )
    for key, expected in (
        ("generator_seed", 872341),
        ("train_episodes", 256),
        ("validation_episodes", 64),
        ("test_episodes_per_family", 64),
        ("queries_per_episode", 8),
    ):
        _fixed_integer(data[key], expected, f"data.{key}")
    _fixed_strings(data["test_families"], _TEST_FAMILIES, "data.test_families")

    training = protocol["training"]
    fields(
        training,
        {
            "backend", "version", "device", "dtype", "threads", "candidate_steps",
            "batch_size", "learning_rate", "betas", "epsilon", "weight_decay",
            "gradient_clip", "validation_fractions", "selection",
        },
        "training",
    )
    for key, expected in (
        ("backend", "torch"), ("version", "2.14.0"), ("device", "cpu"),
        ("dtype", "float32"),
        ("selection", "lowest_validation_cross_entropy_then_earliest"),
    ):
        _fixed_text(training[key], expected, f"training.{key}")
    _fixed_integer(training["threads"], 1, "training.threads")
    if not isinstance(training["candidate_steps"], list) or not training["candidate_steps"]:
        raise ContractError("training.candidate_steps must be a nonempty list")
    for index, steps in enumerate(training["candidate_steps"]):
        integer(steps, f"training.candidate_steps[{index}]")
    if training["candidate_steps"] != [256, 128]:
        raise ContractError("training.candidate_steps differ from registered EXP-0002")
    _fixed_integer(training["batch_size"], 16, "training.batch_size")
    _fixed_number(training["learning_rate"], 0.02, "training.learning_rate")
    _fixed_number_list(training["betas"], [0.9, 0.999], "training.betas")
    _fixed_number(training["epsilon"], 1e-8, "training.epsilon")
    _fixed_number(training["weight_decay"], 0.0, "training.weight_decay")
    _fixed_number(training["gradient_clip"], 1.0, "training.gradient_clip")
    _fixed_number_list(
        training["validation_fractions"], [0.25, 0.5, 1.0], "training.validation_fractions"
    )

    preflight = protocol["preflight"]
    fields(
        preflight,
        {
            "warmup_steps", "timed_steps", "extrapolated_training_seconds",
            "max_wall_seconds", "max_output_bytes",
        },
        "preflight",
    )
    for key, expected in (
        ("warmup_steps", 8), ("timed_steps", 16),
        ("extrapolated_training_seconds", 60),
    ):
        _fixed_integer(preflight[key], expected, f"preflight.{key}")
    integer(
        preflight["max_wall_seconds"], "preflight.max_wall_seconds", 1,
        min(_MAX_WALL_SECONDS, policy["max_wall_seconds"]),
    )
    integer(
        preflight["max_output_bytes"], "preflight.max_output_bytes", 1,
        min(_MAX_OUTPUT_BYTES, policy["max_run_output_bytes"]),
    )

    budget = protocol["budget"]
    fields(
        budget,
        {
            "max_wall_seconds_per_run", "max_output_bytes_per_run",
            "max_query_presentations_per_run", "max_training_attempts", "max_peak_rss_bytes",
        },
        "budget",
    )
    integer(
        budget["max_wall_seconds_per_run"], "budget.max_wall_seconds_per_run", 1,
        min(_MAX_WALL_SECONDS, policy["max_wall_seconds"]),
    )
    integer(
        budget["max_output_bytes_per_run"], "budget.max_output_bytes_per_run", 1,
        min(_MAX_OUTPUT_BYTES, policy["max_run_output_bytes"]),
    )
    integer(
        budget["max_query_presentations_per_run"],
        "budget.max_query_presentations_per_run", 1, _MAX_PRESENTATIONS,
    )
    integer(
        budget["max_training_attempts"], "budget.max_training_attempts",
        len(_ARMS) * len(_SEEDS), len(_ARMS) * len(_SEEDS),
    )
    integer(budget["max_peak_rss_bytes"], "budget.max_peak_rss_bytes", 1, _MAX_PEAK_RSS_BYTES)

    acceptance = protocol["acceptance"]
    fields(
        acceptance,
        {
            "base_accuracy", "all_family_accuracy", "minimum_family_accuracy",
            "dense_difference_ci_low", "ablation_difference_ci_low",
            "max_payload_read_ratio", "interval",
        },
        "acceptance",
    )
    for key, expected in (
        ("base_accuracy", 0.90),
        ("all_family_accuracy", 0.85),
        ("minimum_family_accuracy", 0.75),
        ("dense_difference_ci_low", -0.05),
        ("ablation_difference_ci_low", 0.20),
        ("max_payload_read_ratio", 0.25),
    ):
        _fixed_number(acceptance[key], expected, f"acceptance.{key}")
    _fixed_text(acceptance["interval"], "paired_training_seed_t95_df4", "acceptance.interval")

    if protocol["network_during_run"] is not False:
        raise ContractError("network_during_run must be false")
    if protocol["pretrained_components"] != []:
        raise ContractError("pretrained_components must be empty")

    maximum_presentations = (
        max(training["candidate_steps"]) * training["batch_size"]
        + len(training["validation_fractions"])
        * data["validation_episodes"]
        * data["queries_per_episode"]
        + 2
        * data["test_episodes_per_family"]
        * len(data["test_families"])
        * data["queries_per_episode"]
        + 16
    )
    if maximum_presentations > _MAX_PRESENTATIONS:
        raise ContractError("derived query presentations exceed the registered maximum")
    if maximum_presentations > budget["max_query_presentations_per_run"]:
        raise ContractError("derived query presentations exceed the per-run budget")
    if maximum_presentations > policy["max_cases"]:
        raise ContractError("derived query presentations exceed resource policy max_cases")
