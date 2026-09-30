"""Finite transition world and held-out computations; never imported by a model."""
from __future__ import annotations

from itertools import product
import random

from .contracts import ContractError
from .input_audit import audit_inputs, require_informative_inputs


def world(config: dict) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    rng = random.Random(config["world_seed"])
    result = []
    for _ in range(4):
        permutation = list(range(8))
        rng.shuffle(permutation)
        result.append((tuple(permutation), tuple(rng.randrange(2) for _ in range(8))))
    return result


def transform(config: dict, actions) -> tuple:
    """Canonical signed permutation: equivalence of computations, not answer labels."""
    positions, flips = tuple(range(8)), (0,) * 8
    rules = world(config)
    for action in actions:
        permutation, mask = rules[action]
        positions, flips = (tuple(positions[i] for i in permutation),
                            tuple(flips[i] ^ bit for i, bit in zip(permutation, mask)))
    return positions, flips


def simulate(config: dict, initial: list[int], actions) -> list[list[int]]:
    state, states = initial[:], []
    rules = world(config)
    for action in actions:
        permutation, mask = rules[action]
        state = [state[i] ^ bit for i, bit in zip(permutation, mask)]
        states.append(state)
    return states


def partition(config: dict) -> dict[str, list[int]]:
    # Complement pairs preserve marginal bit balance in every initial-state split.
    pairs = list(range(128))
    random.Random(config["partition_seed"]).shuffle(pairs)
    result, offset = {}, 0
    for name, count in zip(("training", "validation", "development", "final"), config["initial_state_counts"]):
        result[name] = [state for value in pairs[offset:offset + count // 2] for state in (value, value ^ 255)]
        offset += count // 2
    return result


def pairs_in(actions) -> set[tuple[int, int]]:
    return set(zip(actions, actions[1:]))


def training_words(config: dict, length: int) -> list[tuple[int, ...]]:
    excluded = {tuple(pair) for pair in config["development_pairs"] + config["final_pairs"]}
    return [word for word in product(range(4), repeat=length) if not pairs_in(word) & excluded]


def transfer_words(config: dict, partition_name: str, family: str) -> list[tuple[int, ...]]:
    """Enumerate structure only. No final starting states or trajectories are rendered."""
    if partition_name not in {"development", "final"}:
        raise ContractError("unknown transition transfer partition")
    own = {tuple(pair) for pair in config["development_pairs" if partition_name == "development" else "final_pairs"]}
    other = {tuple(pair) for pair in config["final_pairs" if partition_name == "development" else "development_pairs"]}
    trained = {transform(config, word) for length in (1, 2, 3) for word in training_words(config, length)}
    if family == "novel_pair":
        words = sorted(own)
    else:
        length = 6 if family == "longer6" else 4
        words = [word for word in product(range(4), repeat=length)
                 if (bool(pairs_in(word) & own) and not pairs_in(word) & other
                     if family == "novel4" else not pairs_in(word) & (own | other))]
    # Keep reserved four-step words out of every internal window of development
    # six-step words, not just the supervised prefix. Allocation precedes learning.
    if family.startswith("longer"):
        prefixes = {word: index for index, word in enumerate(training_words(config, 4))}
        if partition_name == "development":
            words = [word for word in words if all(prefixes[word[start:start + 4]] % 2 == 0 for start in range(len(word) - 3))]
        else:
            words = [word for word in words if prefixes[word[:4]] % 2 == 1]
    blocked = trained
    if partition_name == "final":
        blocked = blocked | {transform(config, word[start:end]) for name in ("novel_pair", "longer4", "novel4", "longer6")
                             for word in transfer_words(config, "development", name)
                             for start in range(len(word)) for end in range(start + 1, len(word) + 1)}
    return [word for word in words if transform(config, word) not in blocked]


def render(config: dict, state: int, word, family: str) -> dict:
    initial = [(state >> bit) & 1 for bit in range(8)]
    return {"initial": initial, "actions": list(word), "targets": simulate(config, initial, word), "family": family}


def sample(config: dict, states: list[int], words: list[tuple], count: int, seed: int, family: str) -> list[dict]:
    choices = [(state, word) for state in states for word in words]
    if len(choices) < count:
        raise ContractError("transition family has insufficient distinct inputs")
    selected = random.Random(seed).sample(choices, count)
    return [render(config, state, word, family) for state, word in selected]


def generate(protocol: dict, stage: str) -> dict[str, list[dict]]:
    if stage not in protocol["stages"]:
        raise ContractError("unknown transition acquisition stage")
    config, data = protocol["data"], {}
    split = partition(config)
    for name in ("training", "validation"):
        states = split[name][:8] if stage == "tiny" else split[name]
        data[name] = [render(config, state, (action,), "one") for state in states for action in range(4)]
        if stage == "tiny" and name == "validation":
            data[name] = []
        if stage == "mixed":
            for length in (2, 3):
                count = config["mixed_extra_" + name + "_per_length"]
                data[name] += sample(config, states, training_words(config, length), count,
                                     config["partition_seed"] + length + (100 if name == "validation" else 0), "short")
    return data


def transfer(protocol: dict, partition_name: str, *, final_authorized: bool = False) -> list[dict]:
    if partition_name == "final" and not final_authorized:
        raise ContractError("final trajectories require a separate confirmation registration")
    config = protocol["data"]
    states = partition(config)[partition_name]
    rows = [render(config, state, (action,), "one") for state in states for action in range(4)]
    for length in (2, 3):
        rows += sample(config, states, training_words(config, length), 64, config["partition_seed"] + length + 500, "short")
    for i, family in enumerate(("novel_pair", "longer4", "novel4", "longer6")):
        words = transfer_words(config, partition_name, family)
        count = len(states) * len(words) if family == "novel_pair" else config["transfer_per_long_family"]
        rows += sample(config, states, words, count, config["partition_seed"] + 800 + i, family)
    return rows


def input_signature(row: dict) -> tuple:
    # These are exactly the arguments consumed by both forward paths. Neither has
    # pooling, truncation, action sorting or learned positional parameters.
    return tuple(row["initial"]), tuple(row["actions"])


def audit(protocol: dict) -> dict:
    config = protocol["data"]
    groups = generate(protocol, "mixed")
    groups["development"] = transfer(protocol, "development")
    prefixes = {name: [{"initial": row["initial"], "actions": row["actions"][:i + 1], "expected": target}
                       for row in rows for i, target in enumerate(row["targets"])] for name, rows in groups.items()}
    result = audit_inputs(prefixes, input_signature)
    require_informative_inputs(result, disjoint_pairs=("training/validation", "training/development", "validation/development"))
    full_trajectories = {name: {tuple(tuple(state) for state in [row["initial"], *row["targets"]]) for row in rows}
                         for name, rows in groups.items()}
    overlaps = {a + "/" + b: len(full_trajectories[a] & full_trajectories[b])
                for a, b in (("training", "validation"), ("training", "development"), ("validation", "development"))}
    if any(overlaps.values()):
        raise ContractError("latent trajectory overlap")
    counts = {part: {family: len(transfer_words(config, part, family)) for family in ("novel_pair", "longer4", "novel4", "longer6")}
              for part in ("development", "final")}
    if any(not count for families in counts.values() for count in families.values()):
        raise ContractError("empty structural holdout")
    witnesses = []
    for a in range(4):
        for b in range(a + 1, 4):
            for state in partition(config)["training"]:
                first, second = render(config, state, (a, b), "audit"), render(config, state, (b, a), "audit")
                if first["targets"][-1] != second["targets"][-1]:
                    witnesses.append({"initial": first["initial"], "actions_a": [a, b], "actions_b": [b, a],
                                      "target_a": first["targets"][-1], "target_b": second["targets"][-1]})
                    break
    if len(witnesses) != 6:
        raise ContractError("action order lacks all-pair counterexamples")
    return {"actual_input_prefix_audit": result, "latent_trajectory_overlaps": overlaps,
            "structural_word_counts": counts, "order_witnesses": witnesses,
            "scope": "Finite complete input and prefix signatures; fixed preprocessing has no quotient symmetry. Net-transform exclusions cover every allowed training word and prefix, not just sampled rows. Final trajectory labels remain unrendered. Initial-state partitions do not forbid overlap of intermediate target states."}


def score(rows: list[dict], predictions: list[list[int]]) -> dict:
    if len(rows) != len(predictions):
        raise ContractError("transition prediction count differs")
    groups: dict[str, dict] = {}
    for row, prediction in zip(rows, predictions):
        if len(prediction) != 8 or any(type(bit) is not int or bit not in (0, 1) for bit in prediction):
            raise ContractError("transition prediction is not an eight-bit state")
        target = row["targets"][-1]
        keys = ("all", "length/" + str(len(row["actions"])), "action/" + str(row["actions"][-1]), "family/" + row["family"])
        for key in keys:
            item = groups.setdefault(key, {"cases": 0, "exact": 0, "correct_bits": 0, "changed_bits": 0, "correct_changed_bits": 0, "target_ones": 0})
            item["cases"] += 1
            item["exact"] += int(prediction == target)
            item["correct_bits"] += sum(a == b for a, b in zip(prediction, target))
            item["target_ones"] += sum(target)
            for before, truth, actual in zip(row["initial"], target, prediction):
                item["changed_bits"] += int(before != truth)
                item["correct_changed_bits"] += int(before != truth and truth == actual)
    for item in groups.values():
        item["exact_accuracy"] = item["exact"] / item["cases"]
        item["bit_accuracy"] = item["correct_bits"] / (8 * item["cases"])
        item["changed_bit_accuracy"] = item["correct_changed_bits"] / item["changed_bits"] if item["changed_bits"] else None
    return groups
