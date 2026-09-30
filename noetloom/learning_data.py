"""Frozen EXP-0002 generator; observations and scorer-only fields stay separate."""
from __future__ import annotations

import hashlib
import random
from typing import Any

from .contracts import ContractError, canonical_bytes

FAMILIES = ("base", "delay", "capacity", "composition")
DIMENSIONS = {"key": 16, "latent": 8, "values": 4, "capacity": 32}


def key_bits(key: int) -> list[float]:
    return [1.0 if key & (1 << bit) else -1.0 for bit in range(16)]


def key_pools(seed: int) -> dict[str, list[int]]:
    keys = list(range(65536))
    random.Random(seed).shuffle(keys)
    return {"train": keys[:2048], "validation": keys[2048:2560],
            "test": keys[2560:4608], "development": keys[4608:5120]}


def _seed(seed: int, name: str, index: int) -> int:
    return int.from_bytes(hashlib.sha256(f"{seed}:{name}:{index}".encode()).digest()[:8], "big")


def episode(pool: list[int], seed: int, family: str, identity: str) -> dict[str, Any]:
    if family not in FAMILIES:
        raise ContractError(f"unknown learning family: {family}")
    rng = random.Random(seed)
    initial = 16 if family == "capacity" else 4
    distractors = 18 if family == "delay" else 2
    keys = rng.sample(pool, initial + distractors + 1)
    values = {key: rng.randrange(4) for key in keys}
    current: dict[int, int] = {}
    observations: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []

    def write(key: int, value: int) -> None:
        observations.append({"op": "write", "key": key_bits(key), "value": value})
        current[key] = value

    def delete(key: int) -> None:
        observations.append({"op": "delete", "key": key_bits(key)})
        current.pop(key, None)

    def query(key: int, phase: str) -> None:
        query_id = len(answers)
        observations.append({"op": "query", "key": key_bits(key), "query_id": query_id})
        answers.append({"query_id": query_id, "expected": current.get(key, 4), "phase": phase})

    def queries(indices: list[int], phase: str) -> None:
        rng.shuffle(indices)
        for index in indices:
            query(keys[index], phase)

    order = list(range(initial))
    rng.shuffle(order)
    for index in order:
        write(keys[index], values[keys[index]])
    if family == "composition":
        query(keys[0], "initial")
        write(keys[0], (values[keys[0]] + rng.randrange(1, 4)) % 4)
        query(keys[0], "revision")
        delete(keys[1])
        query(keys[1], "deletion")
        # Reinsertion after deletion never occurs in train/validation templates.
        write(keys[1], (values[keys[1]] + rng.randrange(1, 4)) % 4)
        query(keys[1], "reinsertion")
        for key in keys[initial:initial + distractors]:
            write(key, values[key])
        query(keys[2], "delayed")
        write(keys[0], values[keys[0]])
        query(keys[0], "recovery")
        query(keys[3], "retention")
        query(keys[-1], "unknown")
    else:
        queries([0, 1], "initial")
        for key in keys[initial:initial + distractors]:
            write(key, values[key])
        queries([2, 3], "delayed")
        for index in (0, 1):
            write(keys[index], (values[keys[index]] + rng.randrange(1, 4)) % 4)
        delete(keys[2])
        queries([0, 1], "revision")
        query(keys[2], "deletion")
        query(keys[-1], "unknown")
    if len(answers) != 8:
        raise ContractError("generator query count changed")
    return {"id": identity, "observations": observations, "answers": answers}


def generate(protocol: dict[str, Any], *, development: bool = False) -> dict[str, Any]:
    config = protocol["data"]
    seed = config["generator_seed"]
    pools = key_pools(seed)
    specifications = [("development", "development", "base", 32)] if development else [
        ("train", "train", "base", config["train_episodes"]),
        ("validation", "validation", "base", config["validation_episodes"]),
        *((f"test_{family}", "test", family, config["test_episodes_per_family"])
          for family in config["test_families"]),
    ]
    datasets = {
        name: [episode(pools[pool], _seed(seed, name, index), family, f"{name}-{index:04d}")
               for index in range(count)]
        for name, pool, family, count in specifications
    }
    streams = [hashlib.sha256(canonical_bytes(row["observations"])).hexdigest()
               for rows in datasets.values() for row in rows]
    if len(streams) != len(set(streams)):
        raise ContractError("duplicate observable learning episode")
    used_pools = [set(pools[name]) for name in ("train", "validation", "test", "development")]
    if any(left & right for i, left in enumerate(used_pools) for right in used_pools[i + 1:]):
        raise ContractError("learning key pool overlap")
    return {"schema_version": "noetloom.learning_data.v1", "datasets": datasets,
            "pool_sha256": {name: hashlib.sha256(canonical_bytes(keys)).hexdigest()
                            for name, keys in pools.items()},
            "observable_stream_sha256": streams}


def query_prefixes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scored training views. Never pass these dictionaries to a runtime predictor."""
    result = []
    for row in rows:
        events: list[dict[str, Any]] = []
        by_query = {answer["query_id"]: answer for answer in row["answers"]}
        writes = 0
        for observation in row["observations"]:
            if observation["op"] == "query":
                answer = by_query[observation["query_id"]]
                result.append({"key": observation["key"], "events": events[-32:].copy(),
                               "writes": writes, "expected": answer["expected"],
                               "episode_id": row["id"], "query_id": observation["query_id"]})
            else:
                writes += 1
                payload = [0.0] * 5
                payload[observation["value"] if observation["op"] == "write" else 4] = 1.0
                events.append({"key": observation["key"], "input": payload, "written_at": writes})
    return result


def observations_only(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": row["id"], "observations": row["observations"]} for row in rows]


def reference_answers(observations: list[dict[str, Any]]) -> list[int]:
    """Separate exact reference for checking generator labels; never a candidate input."""
    state: dict[tuple[float, ...], int] = {}
    answers = []
    for operation in observations:
        key = tuple(operation["key"])
        if operation["op"] == "write":
            state[key] = operation["value"]
        elif operation["op"] == "delete":
            state.pop(key, None)
        elif operation["op"] == "query":
            answers.append(state.get(key, 4))
        else:
            raise ContractError("unknown reference operation")
    return answers
