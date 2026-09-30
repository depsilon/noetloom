"""EXP-0005 latent partitions and observed-field scorer, separate from model code."""
from __future__ import annotations

import hashlib
import itertools
import random
import struct

from .contracts import ContractError, canonical_bytes

SURFACES = ("ranks", "sequence", "relations")
PERMUTATION = (3, 0, 5, 1, 4, 2)


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def orbit_key(order: tuple, query: tuple) -> tuple:
    inverse = {entity: position for position, entity in enumerate(PERMUTATION)}
    orbit = []
    for _ in range(6):
        orbit.append((order, query))
        order, query = tuple(inverse[e] for e in order), tuple(inverse[e] for e in query)
    return min(orbit)


def partitions(spec: dict) -> dict:
    rng = random.Random(spec["generator_seed"])
    pools = {0: [], 1: []}
    seen = set()
    for order in itertools.permutations(range(6)):
        for query in itertools.permutations(range(6), 2):
            orbit = orbit_key(order, query)
            if orbit not in seen:
                selected_order, selected_query = order, query
                inverse = {entity: position for position, entity in enumerate(PERMUTATION)}
                for _ in range(rng.randrange(6)):
                    selected_order = tuple(inverse[e] for e in selected_order)
                    selected_query = tuple(inverse[e] for e in selected_query)
                pools[int(order.index(query[0]) < order.index(query[1]))].append((selected_order, selected_query))
                seen.add(orbit)
    for pool in pools.values():
        rng.shuffle(pool)
    result = {}
    for name in ("tiny", "training", "validation", "development_transfer", "confirmation"):
        result[name] = [pools[i % 2].pop() for i in range(spec[name + "_problems"])]
        rng.shuffle(result[name])
    return result


def render(order: tuple, query: tuple, surface: str, transform: str = "identity") -> list[float]:
    rank = {entity: index for index, entity in enumerate(order)}
    grid = [[0.0] * 8 for _ in range(8)]
    for entity in range(6):
        if surface == "ranks":
            grid[entity][0] = (rank[entity] - 2.5) / 2.5
        elif surface == "sequence":
            grid[entity][rank[entity]] = 1.0
        elif surface == "relations":
            grid[entity][:6] = [float((rank[entity] < rank[other]) - (rank[entity] > rank[other]))
                               for other in range(6)]
        else:
            raise ContractError("unknown calibration surface")
        grid[entity][6] = float((entity == query[0]) - (entity == query[1]))
        grid[entity][7] = float(SURFACES.index(surface) - 1)
    grid[7][7], grid[7][6], grid[6][7] = 2.0, 1.5, -1.5
    if transform == "row_permutation":
        # Input-independent relabeling; relation columns use the same permutation.
        permutation = PERMUTATION
        rows = [grid[i][:] for i in permutation]
        if surface == "relations":
            rows = [[row[i] for i in permutation] + row[6:] for row in rows]
        grid[:6] = rows
    elif transform == "transpose":
        grid = list(map(list, zip(*grid)))
    elif transform != "identity":
        raise ContractError("unknown calibration transformation")
    return [f32(x) for row in grid for x in row]


def decode(values: list[float]) -> int:
    """Exact observed-field reference; never imported by learned forward code."""
    if len(values) != 64:
        raise ContractError("calibration field needs 64 values")
    grid = [values[i:i + 8] for i in range(0, 64, 8)]
    if (grid[7][7], grid[7][6], grid[6][7]) == (2.0, -1.5, 1.5):
        grid = list(map(list, zip(*grid)))
    if (grid[7][7], grid[7][6], grid[6][7]) != (2.0, 1.5, -1.5):
        raise ContractError("calibration orientation is invalid")
    if any(grid[i][j] != 0 for i in (6, 7) for j in range(6)) or grid[6][6] != 0:
        raise ContractError("calibration unused cells changed")
    formats, marks = [row[7] for row in grid[:6]], [row[6] for row in grid[:6]]
    if len(set(formats)) != 1 or formats[0] not in (-1.0, 0.0, 1.0):
        raise ContractError("invalid calibration format marker")
    if marks.count(1.0) != 1 or marks.count(-1.0) != 1 or marks.count(0.0) != 4:
        raise ContractError("invalid calibration query")
    first, second = marks.index(1.0), marks.index(-1.0)
    block = [row[:6] for row in grid[:6]]
    if formats[0] == -1:
        ranks = [row[0] for row in block]
        if any(value != 0 for row in block for value in row[1:]) or sorted(ranks) != list(map(f32, [-1.0, -0.6, -0.2, 0.2, 0.6, 1.0])):
            raise ContractError("invalid calibration rank grammar")
        return int(ranks[first] < ranks[second])
    if formats[0] == 0:
        if (any(set(row) - {0.0, 1.0} or sum(row) != 1 for row in block)
                or any(sum(row[j] for row in block) != 1 for j in range(6))):
            raise ContractError("invalid calibration sequence grammar")
        return int(block[first].index(1.0) < block[second].index(1.0))
    degrees = [row.count(1.0) for row in block]
    if sorted(degrees) != list(range(6)) or any(
            block[i][j] != float((degrees[i] > degrees[j]) - (degrees[i] < degrees[j]))
            for i in range(6) for j in range(6)):
        raise ContractError("invalid calibration relation grammar")
    return int(block[first][second] == 1.0)


def rows(problems: list, surfaces: tuple = SURFACES, transform: str = "identity") -> list[dict]:
    result = []
    for order, query in problems:
        for surface in surfaces:
            values = render(order, query, surface, transform)
            expected = int(order.index(query[0]) < order.index(query[1]))
            if decode(values) != expected:
                raise ContractError("independent decoder and generator disagree")
            result.append({"values": values, "expected": expected, "surface": surface,
                           "transform": transform, "latent": [list(order), list(query)],
                           "input_sha256": hashlib.sha256(canonical_bytes(values)).hexdigest()})
    return result


def generate(protocol: dict, stage: str, *, confirmation: bool = False, include_evaluation: bool = True) -> dict:
    if stage not in protocol["stages"]:
        raise ContractError("unknown calibration stage")
    split = partitions(protocol["data"])
    surfaces = SURFACES if stage == "mixed" else ("ranks",)
    training = rows(split["tiny" if stage == "tiny" else "training"], surfaces)
    result = {"training": training, "validation": [] if stage == "tiny" else rows(split["validation"], surfaces)}
    if stage == "mixed" and include_evaluation:
        name = "confirmation" if confirmation else "development_transfer"
        transforms = ("identity", *protocol["data"]["transforms"]) if confirmation else protocol["data"]["transforms"]
        result["evaluation"] = [row for transform in transforms for row in rows(split[name], surfaces, transform)]
    else:
        result["evaluation"] = []
    # Multi-view rows deliberately share latent problems within a split; never across splits.
    used_keys, used_inputs = set(), set()
    for group in result.values():
        keys = {canonical_bytes(row["latent"]) for row in group}
        hashes = {row["input_sha256"] for row in group}
        if used_keys & keys or used_inputs & hashes or len(hashes) != len(group):
            raise ContractError("latent problems or observed inputs overlap partitions")
        used_keys |= keys
        used_inputs |= hashes
    return result


def score(cases: list[dict], predictions: list[int]) -> dict:
    if len(cases) != len(predictions) or any(type(p) is not int or p not in (0, 1) for p in predictions):
        raise ContractError("invalid calibration predictions")
    counts = {}
    for row, prediction in zip(cases, predictions):
        expected = decode(row["values"])
        if expected != row["expected"]:
            raise ContractError("calibration label differs from observed reference")
        key = row["transform"] + "/" + row["surface"]
        entry = counts.setdefault(key, {"correct": 0, "total": 0, "class_support": [0, 0]})
        entry["correct"] += int(prediction == expected)
        entry["total"] += 1
        entry["class_support"][expected] += 1
    for entry in counts.values():
        entry["accuracy"] = entry["correct"] / entry["total"]
    return counts
