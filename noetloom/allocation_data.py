"""EXP-0003 observations; excludes every key pool used by the parent experiment."""
from __future__ import annotations

import hashlib
import random

from .contracts import ContractError, canonical_bytes
from .learning_data import _seed, episode, key_bits, key_pools as parent_pools

FAMILIES = ("base", "delay", "capacity", "interleaved")


def key_pools(seed: int = 981733) -> dict[str, list[int]]:
    excluded = {key for values in parent_pools(872341).values() for key in values}
    keys = [key for key in range(65536) if key not in excluded]
    random.Random(seed).shuffle(keys)
    return {"train": keys[:1024], "validation": keys[1024:1280],
            "test": keys[1280:3328], "development": keys[3328:3456]}


def shifted_episode(pool: list[int], seed: int, family: str, identity: str) -> dict:
    if family in {"base", "delay"}:
        return episode(pool, seed, family, identity)
    if family not in {"capacity", "interleaved"}:
        raise ContractError("unknown allocation family")
    rng = random.Random(seed)
    initial = 28 if family == "capacity" else 4
    keys = rng.sample(pool, initial + 3)
    values = {key: rng.randrange(4) for key in keys}
    observations, answers = [], []
    current: dict[int, int] = {}

    def write(index: int, value: int) -> None:
        observations.append({"op": "write", "key": key_bits(keys[index]), "value": value})
        current[keys[index]] = value

    def delete(index: int) -> None:
        observations.append({"op": "delete", "key": key_bits(keys[index])})
        current.pop(keys[index], None)

    def query(index: int, phase: str) -> None:
        query_id = len(answers)
        observations.append({"op": "query", "key": key_bits(keys[index]), "query_id": query_id})
        answers.append({"query_id": query_id, "expected": current.get(keys[index], 4), "phase": phase})

    order = list(range(initial))
    rng.shuffle(order)
    for index in order:
        write(index, values[keys[index]])
    query(0, "initial")
    query(1, "initial")
    if family == "capacity":
        for index in (initial, initial + 1):
            write(index, values[keys[index]])
        query(2, "delayed")
        query(3, "delayed")
        for index in (0, 1):
            write(index, (values[keys[index]] + rng.randrange(1, 4)) % 4)
        delete(2)
        query(0, "revision")
        query(1, "revision")
        query(2, "deletion")
    else:
        delete(0)
        write(1, (values[keys[1]] + rng.randrange(1, 4)) % 4)
        query(0, "deletion")
        write(0, (values[keys[0]] + rng.randrange(1, 4)) % 4)
        query(1, "revision")
        for index in (initial, initial + 1):
            write(index, values[keys[index]])
        query(0, "reinsertion")
        delete(1)
        query(1, "deletion")
        write(1, values[keys[1]])
        query(1, "recovery")
    query(initial + 2, "unknown")
    if len(answers) != 8:
        raise ContractError("allocation generator must produce eight queries")
    return {"id": identity, "observations": observations, "answers": answers}


def generate(protocol: dict, *, development: bool = False) -> dict:
    config = protocol["data"]
    seed = config["generator_seed"]
    pools = key_pools(seed)
    specifications = [("development", "development", "base", config["development_episodes"])] if development else [
        ("train", "train", "base", config["train_episodes"]),
        ("validation", "validation", "base", config["validation_episodes"]),
        *((f"test_{family}", "test", family, config["test_episodes_per_family"])
          for family in config["test_families"]),
    ]
    datasets = {name: [shifted_episode(pools[pool], _seed(seed, name, index), family,
                                     f"{name}-{index:04d}") for index in range(count)]
                for name, pool, family, count in specifications}
    streams = [hashlib.sha256(canonical_bytes(row["observations"])).hexdigest()
               for rows in datasets.values() for row in rows]
    if len(streams) != len(set(streams)):
        raise ContractError("duplicate observable allocation episode")
    return {"schema_version": "noetloom.allocation_data.v1", "datasets": datasets,
            "pool_sha256": {name: hashlib.sha256(canonical_bytes(keys)).hexdigest()
                            for name, keys in pools.items()},
            "observable_stream_sha256": streams}
