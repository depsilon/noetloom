"""EXP-0004 raw fields; latent generation and independent field decoding stay outside models."""
from __future__ import annotations

import hashlib
import itertools
import math
import random
import struct

from .contracts import ContractError, canonical_bytes, fields

SURFACES = ("ranks", "sequence", "relations")
FAMILIES = ("base", "combination", "reflection", "joint")
SEEN = {"ranks": (0, 1, 2), "sequence": (1, 2, 3), "relations": (0, 2, 3)}
HELDOUT = {"ranks": 3, "sequence": 0, "relations": 1}


def rotate(grid: list[list[float]]) -> list[list[float]]:
    return [list(row) for row in zip(*grid[::-1])]


def transform(grid: list[list[float]], turns: int, reflected: bool) -> list[float]:
    result = [row[::-1] if reflected else row[:] for row in grid]
    for _ in range(turns):
        result = rotate(result)
    return [value for row in result for value in row]


def render(order: tuple[int, ...], query: tuple[int, int], surface: str,
           turns: int, reflected: bool, rng: random.Random) -> list[float]:
    if sorted(order) != list(range(5)) or len(set(query)) != 2 or not set(query) <= set(order):
        raise ContractError("invalid latent order problem")
    if surface not in SURFACES or type(turns) is not int or not 0 <= turns <= 3 or type(reflected) is not bool:
        raise ContractError("invalid surface transformation")
    grid = [[0.0] * 8 for _ in range(8)]
    if surface == "ranks":
        for rank, entity in enumerate(order):
            grid[entity][0] = (rank - 2) * 0.4 + rng.uniform(-0.08, 0.08)
    elif surface == "sequence":
        for rank, entity in enumerate(order):
            grid[rank][entity] = 1.0
    else:
        ranks = {entity: rank for rank, entity in enumerate(order)}
        for left in range(5):
            for right in range(5):
                grid[left][right] = float((ranks[left] < ranks[right]) - (ranks[left] > ranks[right]))
    grid[5][query[0]], grid[5][query[1]] = 1.0, -1.0
    grid[7][7], grid[7][6], grid[6][7] = 2.0, 1.5, -1.5
    # Freeze the actual float32 values received by both execution backends.
    return [struct.unpack("<f", struct.pack("<f", value))[0]
            for value in transform(grid, turns, reflected)]


def decode(values: list[float]) -> int:
    """Independent exact scorer: recover orientation, grammar and order from observed bytes.

    It does not consume generator metadata or a supplied latent order. Never imported by
    the tensor model or native forward path.
    """
    if (not isinstance(values, list) or len(values) != 64
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in values)):
        raise ContractError("field needs 64 finite numbers")
    source = [values[row * 8:(row + 1) * 8] for row in range(8)]
    oriented = []
    for reflection in (False, True):
        for turns in range(4):
            flat = transform(source, turns, reflection)
            if (flat[63], flat[62], flat[55]) == (2.0, 1.5, -1.5):
                oriented.append([flat[row * 8:(row + 1) * 8] for row in range(8)])
    if len(oriented) != 1:
        raise ContractError("field orientation is missing or ambiguous")
    grid = oriented[0]
    permitted = {(i, j) for i in range(5) for j in range(5)}
    permitted |= {(5, j) for j in range(5)} | {(7, 7), (7, 6), (6, 7)}
    if any(grid[i][j] != 0 for i in range(8) for j in range(8) if (i, j) not in permitted):
        raise ContractError("nonzero field outside grammar")
    marks = grid[5][:5]
    if marks.count(1.0) != 1 or marks.count(-1.0) != 1 or marks.count(0.0) != 3:
        raise ContractError("field query marks are invalid")
    first, second = marks.index(1.0), marks.index(-1.0)
    block = [row[:5] for row in grid[:5]]
    if all(block[i][j] == 0 for i in range(5) for j in range(1, 5)):
        ranks = [row[0] for row in block]
        ordered = sorted(ranks)
        if any(abs(value - (i - 2) * 0.4) > 0.0800001 for i, value in enumerate(ordered)):
            raise ContractError("numeric surface violates rank intervals")
        return int(ranks[first] < ranks[second])
    if (all(set(row) <= {0.0, 1.0} and sum(row) == 1 for row in block)
            and all(sum(row[column] for row in block) == 1 for column in range(5))):
        positions = [next(i for i, row in enumerate(block) if row[entity] == 1) for entity in range(5)]
        return int(positions[first] < positions[second])
    if any(block[i][i] != 0 for i in range(5)):
        raise ContractError("relation surface has nonzero diagonal")
    if any(block[i][j] not in (-1.0, 1.0) or block[i][j] != -block[j][i]
           for i in range(5) for j in range(5) if i != j):
        raise ContractError("relation surface is not antisymmetric")
    # A total order tournament has distinct out-degrees 0..4; check all implied edges.
    degrees = [sum(value == 1 for value in row) for row in block]
    if sorted(degrees) != list(range(5)) or any(
            block[i][j] != (1.0 if degrees[i] > degrees[j] else -1.0)
            for i in range(5) for j in range(5) if i != j):
        raise ContractError("relation surface does not encode a total order")
    return int(block[first][second] == 1)


def input_hash(values: list[float]) -> str:
    return hashlib.sha256(canonical_bytes(values)).hexdigest()


def observations(cases: list[dict]) -> dict:
    """Copy only actual fields across the inference boundary, stripping scorer context."""
    return {"schema_version": "noetloom.representation_inputs.v1",
            "samples": [{"values": list(case["values"])} for case in cases]}


def validate_observations(value: dict) -> None:
    fields(value, {"schema_version", "samples"}, "representation observations")
    if value["schema_version"] != "noetloom.representation_inputs.v1":
        raise ContractError("unsupported representation observation schema")
    samples = value["samples"]
    if not isinstance(samples, list) or not 1 <= len(samples) <= 512:
        raise ContractError("representation input needs 1–512 samples")
    for sample in samples:
        fields(sample, {"values"}, "representation sample")
        values = sample["values"]
        if (not isinstance(values, list) or len(values) != 64
                or any(type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 2 for x in values)):
            raise ContractError("representation sample requires 64 finite field values in [-2,2]")


def score(cases: list[dict], predictions: list[int]) -> dict:
    if len(predictions) != len(cases) or any(type(p) is not int or p not in (0, 1) for p in predictions):
        raise ContractError("prediction count or class differs from registered cases")
    counts: dict[str, list[int]] = {}
    for case, prediction in zip(cases, predictions):
        expected = decode(case["values"])
        if expected != case["expected"]:
            raise ContractError("rendered-field reference disagrees with latent answer")
        key = case["family"]
        correct, total = counts.setdefault(key, [0, 0])
        counts[key] = [correct + int(prediction == expected), total + 1]
    return {key: {"correct": correct, "total": total, "accuracy": correct / total}
            for key, (correct, total) in counts.items()}


def generate(protocol: dict) -> dict:
    """Freeze one dataset. Latent keys and actual observations are split-checked separately."""
    spec = protocol["data"]
    rng = random.Random(spec["generator_seed"])
    pools: dict[int, list[tuple[tuple[int, ...], tuple[int, int]]]] = {0: [], 1: []}
    for order in itertools.permutations(range(5)):
        for pair in itertools.permutations(range(5), 2):
            label = int(order.index(pair[0]) < order.index(pair[1]))
            pools[label].append((order, pair))
    for pool in pools.values():
        rng.shuffle(pool)
    used_hashes: set[str] = set()
    used_keys: set[tuple] = set()

    def sample_group(count: int, family: str, diagnostic: bool = False) -> list[dict]:
        cases = []
        for index in range(count):
            label = index % 2
            order, query = pools[label].pop()
            latent_key = (order, query)
            if latent_key in used_keys:
                raise ContractError("latent problem overlaps splits")
            used_keys.add(latent_key)
            surfaces = SURFACES if diagnostic else (SURFACES[(index // 2) % 3],)
            for surface in surfaces:
                heldout = family in {"combination", "joint", "diagnostic"}
                turns = HELDOUT[surface] if heldout else rng.choice(SEEN[surface])
                reflected = family in {"reflection", "joint"}
                values = render(order, query, surface, turns, reflected, rng)
                digest = input_hash(values)
                if digest in used_hashes:
                    raise ContractError("actual representation inputs overlap splits")
                used_hashes.add(digest)
                if decode(values) != label:
                    raise ContractError("generator and independent field reference disagree")
                cases.append({"values": values, "expected": label, "family": family,
                              "surface": surface, "rotation": turns, "reflected": reflected,
                              "latent_order": list(order), "latent_query": list(query),
                              "problem_index": index, "input_sha256": digest})
        # Shuffle complete ordinary groups so a scorer-only index cannot correlate with labels.
        if not diagnostic:
            rng.shuffle(cases)
        return cases

    result = {"schema_version": "noetloom.representation_data.v1",
              "training": sample_group(spec["training_cases"], "training"),
              "validation": sample_group(spec["validation_cases"], "validation"),
              "development": sample_group(spec["development_cases"], "development")}
    result["test"] = [case for family in FAMILIES
                      for case in sample_group(spec["test_cases_per_family"], family)]
    result["diagnostic"] = sample_group(spec["diagnostic_problems"], "diagnostic", True)
    result["integrity"] = {"latent_problems": len(used_keys), "unique_observations": len(used_hashes),
                           "supervision": "answer only; no paired views during fitting"}
    return result
