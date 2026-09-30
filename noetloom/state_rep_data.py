"""Fresh finite-world observations and state-reuse cases; never imported by a learner."""
from __future__ import annotations

from functools import lru_cache
from itertools import product
import random

from .contracts import ContractError
from .input_audit import audit_inputs, require_informative_inputs


@lru_cache(maxsize=8)
def rules(seed: int) -> tuple:
    rng, result = random.Random(seed), []
    for _ in range(4):
        permutation = list(range(10))
        rng.shuffle(permutation)
        result.append((tuple(permutation), tuple(rng.randrange(2) for _ in range(10))))
    return tuple(result)


@lru_cache(maxsize=16384)
def net(seed: int, actions: tuple[int, ...]) -> tuple:
    positions, flips = tuple(range(10)), (0,) * 10
    for action in actions:
        permutation, mask = rules(seed)[action]
        positions, flips = (tuple(positions[i] for i in permutation),
                            tuple(flips[i] ^ bit for i, bit in zip(permutation, mask)))
    return positions, flips


def path(config: dict, initial: int, actions) -> list[int]:
    states, current = [initial], initial
    for action in actions:
        permutation, mask = rules(config["world_seed"])[action]
        current = sum((((current >> source) & 1) ^ bit) << target
                      for target, (source, bit) in enumerate(zip(permutation, mask)))
        states.append(current)
    return states


def partition(config: dict) -> dict[str, list[int]]:
    pairs = list(range(512))
    random.Random(config["partition_seed"]).shuffle(pairs)
    result, offset = {}, 0
    for name, count in zip(("training", "validation", "development", "final"), config["state_counts"]):
        result[name] = [state for value in pairs[offset:offset + count // 2] for state in (value, value ^ 1023)]
        offset += count // 2
    return result


def observe(config: dict, state: int, observation: str) -> list[float]:
    if observation not in {"aligned", "nonlinear"} or type(state) is not int or not 0 <= state < 1024:
        raise ContractError("unregistered state observation")
    canonical = [float(2 * ((state >> bit) & 1) - 1) for bit in range(10)]
    result = canonical[:]
    if observation == "nonlinear":
        for target, a, b in config["nonlinear_shears"]:
            result[target] += config["nonlinear_coefficient"] * canonical[a] * canonical[b]
    return result


def render(config: dict, observation: str, initial: int, word, family: str) -> dict:
    states = path(config, initial, word)
    return {"initial": observe(config, initial, observation), "actions": list(word),
            "targets": [observe(config, state, observation) for state in states[1:]], "family": family}


def pairs_in(word) -> set[tuple[int, int]]:
    return set(zip(word, word[1:]))


def training_words(config: dict, length: int) -> list[tuple]:
    forbidden = {tuple(pair) for pair in config["development_pairs"] + config["final_pairs"]}
    return [word for word in product(range(4), repeat=length) if not pairs_in(word) & forbidden]


def transfer_words(config: dict, split: str, family: str) -> list[tuple]:
    if split not in {"development", "final"} or family not in {"novel_pair", "longer4", "novel4", "longer6"}:
        raise ContractError("unregistered structural holdout")
    own = {tuple(pair) for pair in config[split + "_pairs"]}
    other = {tuple(pair) for pair in config["final_pairs" if split == "development" else "development_pairs"]}
    learned = {net(config["world_seed"], word) for length in (1, 2, 3) for word in training_words(config, length)}
    if family == "novel_pair":
        words = sorted(own)
    else:
        length = 6 if family == "longer6" else 4
        words = [word for word in product(range(4), repeat=length)
                 if (bool(pairs_in(word) & own) and not pairs_in(word) & other
                     if family == "novel4" else not pairs_in(word) & (own | other))]
    if family.startswith("longer"):
        indices = {word: i for i, word in enumerate(training_words(config, 4))}
        words = [word for word in words if (all(indices[word[i:i + 4]] % 2 == 0 for i in range(len(word) - 3))
                 if split == "development" else indices[word[:4]] % 2 == 1)]
    if split == "final":
        learned |= {net(config["world_seed"], word[a:b])
                    for name in ("novel_pair", "longer4", "novel4", "longer6")
                    for word in transfer_words(config, "development", name)
                    for a in range(len(word)) for b in range(a + 1, len(word) + 1)}
        for row in continuation_raw({"data": config}):
            for key in ("history_a", "history_b"):
                word = row[key][1] + row["suffix"]
                learned |= {net(config["world_seed"], word[a:b])
                            for a in range(len(word)) for b in range(a + 1, len(word) + 1)}
    return [word for word in words if net(config["world_seed"], word) not in learned]


def sample(config: dict, split: str, words: list[tuple], count: int, salt: int) -> list[tuple[int, tuple]]:
    if split not in {"training", "validation", "development"} or count % 2:
        raise ContractError("sampling needs an admitted non-final split and complement pairs")
    partitions = partition(config)
    allowed = set(partitions["training"] + partitions[split])
    choices = [(state, word) for state in partitions[split] if state < 512 for word in words
               if all(value in allowed for value in path(config, state, word))]
    if len(choices) < count // 2:
        raise ContractError(f"insufficient admitted state paths: {split}, length {len(words[0])}, {len(choices) * 2} < {count}")
    selected = random.Random(config["partition_seed"] + salt).sample(choices, count // 2)
    return [(value, word) for state, word in selected for value in (state, state ^ 1023)]


def acquisition_raw(protocol: dict, stage: str) -> dict[str, list[tuple]]:
    if stage not in {"tiny", "one", "mixed"}:
        raise ContractError("unregistered acquisition stage")
    config, result = protocol["data"], {}
    for split in ("training", "validation"):
        if stage == "tiny" and split == "validation":
            result[split] = []
            continue
        count = config["one_" + split + "_per_action"]
        rows = [(state, word, "one") for action in range(4)
                for state, word in sample(config, split, [(action,)], count, 10 + action + (100 if split == "validation" else 0))]
        if stage == "tiny":
            rows = [row for action in range(4) for row in [r for r in rows if r[1] == (action,)][:8]]
        if stage == "mixed":
            for length in (2, 3):
                rows += [(state, word, "short") for state, word in sample(config, split, training_words(config, length),
                         config["mixed_" + split + "_per_length"], 200 + length + (100 if split == "validation" else 0))]
        result[split] = rows
    return result


def generate(protocol: dict, observation: str, stage: str) -> dict[str, list[dict]]:
    return {split: [render(protocol["data"], observation, state, word, family) for state, word, family in rows]
            for split, rows in acquisition_raw(protocol, stage).items()}


def development_raw(protocol: dict) -> list[tuple]:
    config = protocol["data"]
    result = [(state, word, "one") for action in range(4) for state, word in sample(config, "development", [(action,)],
              config["development_one_per_action"], 500 + action)]
    for length in (2, 3):
        result += [(state, word, "short") for state, word in sample(config, "development", training_words(config, length),
                   config["development_short_per_length"], 600 + length)]
    for i, family in enumerate(("novel_pair", "longer4", "novel4", "longer6")):
        count = config["development_novel_pairs"] if family == "novel_pair" else config["development_per_long_family"]
        result += [(state, word, family) for state, word in sample(config, "development", transfer_words(config, "development", family), count, 700 + i)]
    return result


def development(protocol: dict, observation: str) -> list[dict]:
    return [render(protocol["data"], observation, state, word, family) for state, word, family in development_raw(protocol)]


def continuation_raw(protocol: dict) -> list[dict]:
    config = protocol["data"]
    partitions = partition(config)
    allowed, ends = set(partitions["training"] + partitions["development"]), set(partitions["development"])
    by_end = {end: {2: [], 3: []} for end in ends}
    for length in (2, 3):
        for state in partitions["development"]:
            for word in training_words(config, length):
                states = path(config, state, word)
                if states[-1] in ends and all(s in allowed for s in states):
                    by_end[states[-1]][length].append((state, word))
    rng, result, used = random.Random(config["partition_seed"] + 901), [], set()
    forbidden = {tuple(pair) for pair in config["final_pairs"]}
    trained = {net(config["world_seed"], word) for length in (1, 2, 3) for word in training_words(config, length)}
    for family in ("novel_pair", "longer4", "novel4", "longer6"):
        candidates = []
        for end, histories in sorted(by_end.items()):
            if end in used:
                continue
            for suffix in transfer_words(config, "development", family):
                if not all(s in allowed for s in path(config, end, suffix)):
                    continue
                first = [h for h in histories[2] if not pairs_in(h[1] + suffix) & forbidden
                         and net(config["world_seed"], h[1] + suffix) not in trained]
                second = [h for h in histories[3] if not pairs_in(h[1] + suffix) & forbidden
                          and net(config["world_seed"], h[1] + suffix) not in trained]
                if first and second:
                    a, b = first[0], second[0]
                    if net(config["world_seed"], a[1]) != net(config["world_seed"], b[1]):
                        candidates.append({"state": end, "history_a": a, "history_b": b, "suffix": suffix, "family": family})
                    break
        rng.shuffle(candidates)
        count = config["continuation_pairs_per_family"]
        if len(candidates) < count:
            raise ContractError("insufficient independent common-state continuation cases")
        selected = candidates[:count]
        result += selected
        used.update(row["state"] for row in selected)
    return result


def continuations(protocol: dict, observation: str) -> list[dict]:
    config, result = protocol["data"], []
    for row in continuation_raw(protocol):
        state, word = row["state"], row["suffix"]
        result.append({"history_a": render(config, observation, *row["history_a"], "history"),
                       "history_b": render(config, observation, *row["history_b"], "history"),
                       "current": observe(config, state, observation), "suffix": list(word),
                       "targets": [observe(config, s, observation) for s in path(config, state, word)[1:]],
                       "family": row["family"]})
    return result


def signature(row: dict) -> tuple:
    return tuple(row["initial"]), tuple(row["actions"])


def audit(protocol: dict, observation: str) -> dict:
    config = protocol["data"]
    raw = acquisition_raw(protocol, "mixed")
    raw["development"] = development_raw(protocol)
    groups = {split: [render(config, observation, *row) for row in rows] for split, rows in raw.items()}
    prefixes = {split: [{"initial": row["initial"], "actions": row["actions"][:i + 1], "expected": target}
                       for row in rows for i, target in enumerate(row["targets"])] for split, rows in groups.items()}
    inputs = audit_inputs(prefixes, signature)
    require_informative_inputs(inputs, disjoint_pairs=("training/validation", "training/development", "validation/development"))
    seen = {split: {s for state, word, _ in rows for s in path(config, state, word)} for split, rows in raw.items()}
    partitions = partition(config)
    if any(seen["training"] & set(partitions[split]) for split in ("validation", "development", "final")):
        raise ContractError("training or reconstruction exposes held-out states")
    all_observed = {s for states in seen.values() for s in states}
    if len({tuple(observe(config, s, observation)) for s in all_observed}) != len(all_observed):
        raise ContractError("observation mapping loses state information")
    for split, states in seen.items():
        if states - set(partitions["training"] + partitions[split]):
            raise ContractError("a path crossed its admitted state partitions")
    continuations_raw = continuation_raw(protocol)
    if len({row["state"] for row in continuations_raw}) != 64:
        raise ContractError("continuation end-state support differs")
    words = {split: {family: len(transfer_words(config, split, family)) for family in ("novel_pair", "longer4", "novel4", "longer6")}
             for split in ("development", "final")}
    if any(not count for counts in words.values() for count in counts.values()):
        raise ContractError("empty unseen computation family")
    sensitivity = {}
    for state, word, family in raw["development"]:
        item = sensitivity.setdefault(family, {"cases": 0, "order_changes_endpoint": 0})
        item["cases"] += 1
        item["order_changes_endpoint"] += int(path(config, state, word)[-1] != path(config, state, tuple(reversed(word)))[-1])
    if any(v["order_changes_endpoint"] == 0 for k, v in sensitivity.items() if k != "one"):
        raise ContractError("order control is insensitive for a composition family")
    return {"input_prefix_audit": inputs, "seen_observation_states": {k: len(v) for k, v in seen.items()},
            "training_auxiliary_heldout_state_overlap": 0, "observation_injective_on_audited_states": True,
            "structural_word_counts": words, "reverse_order_sensitivity": sensitivity,
            "continuation_pairs": len(continuations_raw), "continuation_unique_current_states": 64,
            "scope": "Initial observations and reconstruction targets are audited. Training sees no held-out state; later prefixes may revisit training states. Net computations exclude all permitted training subwords. Final word structures are counted, but final trajectories are never rendered."}
