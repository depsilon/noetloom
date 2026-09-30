"""Synthetic mutable recall with explicit nonlearned positive/negative controls."""

from __future__ import annotations

import hashlib
import random
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable

from .contracts import CONTROLS, PHASES, ContractError, canonical_bytes


@dataclass(frozen=True)
class Event:
    kind: str
    key: str
    value: int | None = None
    phase: str | None = None

    def observation(self) -> dict[str, Any]:
        # Neither phase labels nor expected answers enter a control's input.
        return {"kind": self.kind, "key": self.key, "value": self.value}


def make_episode(protocol: dict[str, Any], split: dict[str, Any], seed: int, index: int) -> list[Event]:
    seed_material = canonical_bytes(["mutable_recall_v1", split["name"], seed, index])
    rng = random.Random(int.from_bytes(hashlib.sha256(seed_material).digest(), "big"))
    count = split["memory_slots"]
    keys = [f"key-{number}" for number in range(count)]
    rng.shuffle(keys)
    values = {key: rng.randrange(protocol["value_count"]) for key in keys}
    events = [Event("write", key, values[key]) for key in keys]
    events += [Event("query", key, phase="initial") for key in keys]
    events += [Event("write", f"distractor-{number}", rng.randrange(protocol["value_count"]))
               for number in range(split["distractors"])]
    events += [Event("query", key, phase="delayed") for key in keys]
    for key in keys[:split["updates"]]:
        changed = (values[key] + rng.randrange(1, protocol["value_count"])) % protocol["value_count"]
        events += [Event("write", key, changed), Event("query", key, phase="revision")]
    for key in keys[-split["deletes"]:]:
        events += [Event("delete", key), Event("query", key, phase="deletion")]
    events.append(Event("query", "never-observed", phase="unknown"))
    return events


class MemoryControl:
    """A hand-written control, not a model, learner, or reasoning primitive."""

    def __init__(self, name: str, capacity: int):
        if name not in CONTROLS:
            raise ContractError(f"unknown control: {name}")
        self.name = name
        self.capacity = capacity
        self.state: OrderedDict[str, int] = OrderedDict()

    def observe(self, kind: str, key: str, value: int | None) -> None:
        if self.name == "no_memory":
            return
        if kind == "write":
            if type(value) is not int:
                raise ContractError("write needs an integer value")
            if self.name == "stale_memory":
                self.state.setdefault(key, value)
            else:
                self.state[key] = value
                self.state.move_to_end(key)
                if self.name == "bounded_memory":
                    while len(self.state) > self.capacity:
                        self.state.popitem(last=False)
        elif kind == "delete" and self.name != "stale_memory":
            self.state.pop(key, None)

    def predict(self, key: str) -> int | None:
        return self.state.get(key)


def _score() -> dict[str, Any]:
    return {"correct": 0, "total": 0}


def evaluate(protocol: dict[str, Any], emit: Callable[[dict[str, Any]], None],
             checkpoint: Callable[[], None] = lambda: None) -> dict[str, Any]:
    """Replay identical observations for every control; labels stay in the scorer."""
    metrics: dict[str, Any] = {}
    hashes: dict[str, list[str]] = {split["name"]: [] for split in protocol["splits"]}
    seen: dict[str, str] = {}
    episodes = 0
    predictions = 0
    for split in protocol["splits"]:
        split_metrics = {
            control: {phase: _score() for phase in PHASES} for control in protocol["controls"]
        }
        metrics[split["name"]] = split_metrics
        for seed in protocol["seeds"]:
            for index in range(split["episodes"]):
                checkpoint()
                events = make_episode(protocol, split, seed, index)
                episode_hash = hashlib.sha256(canonical_bytes([e.observation() for e in events])).hexdigest()
                if episode_hash in seen:
                    raise ContractError(f"duplicate episode input in {split['name']} and {seen[episode_hash]}")
                seen[episode_hash] = split["name"]
                hashes[split["name"]].append(episode_hash)
                episodes += 1
                controls = {name: MemoryControl(name, protocol["bounded_memory_slots"])
                            for name in protocol["controls"]}
                truth: dict[str, int] = {}
                for position, event in enumerate(events):
                    checkpoint()
                    if event.kind == "write":
                        assert event.value is not None
                        truth[event.key] = event.value
                    elif event.kind == "delete":
                        truth.pop(event.key, None)
                    elif event.kind == "query":
                        expected = truth.get(event.key)
                        for name, control in controls.items():
                            predicted = control.predict(event.key)
                            correct = predicted == expected
                            row = split_metrics[name][event.phase]
                            row["correct"] += int(correct)
                            row["total"] += 1
                            predictions += 1
                            emit({
                                "split": split["name"], "seed": seed, "episode": index,
                                "position": position, "phase": event.phase, "control": name,
                                "key": event.key, "expected": expected, "predicted": predicted,
                                "correct": correct,
                            })
                    else:
                        raise ContractError(f"unknown event: {event.kind}")
                    if event.kind != "query":
                        for control in controls.values():
                            control.observe(event.kind, event.key, event.value)
    totals = {name: _score() for name in protocol["controls"]}
    for split_rows in metrics.values():
        for name, phases in split_rows.items():
            for score in phases.values():
                totals[name]["correct"] += score["correct"]
                totals[name]["total"] += score["total"]
    for score in totals.values():
        score["accuracy"] = score["correct"] / score["total"]
    def all_wrong(name: str, phases: tuple[str, ...]) -> bool:
        return all(rows[name][phase]["total"] > 0 and rows[name][phase]["correct"] == 0
                   for rows in metrics.values() for phase in phases)

    checks = {
        "exact_reference": totals["exact_memory"]["accuracy"] == 1.0,
        "negative_controls_sensitive": all(totals[name]["accuracy"] < 1.0
                                           for name in protocol["acceptance"]["negative_controls_must_fail"]),
        "episode_inputs_disjoint": True,
        "absent_memory_known_queries_fail": all_wrong("no_memory", ("initial", "delayed", "revision")),
        "stale_updates_and_deletes_fail": all_wrong("stale_memory", ("revision", "deletion")),
        "bounded_delayed_recall_sensitive": any(
            rows["bounded_memory"]["delayed"]["correct"] < rows["bounded_memory"]["delayed"]["total"]
            for rows in metrics.values()
        ),
    }
    return {
        "verdict": "passed" if all(checks.values()) else "failed",
        "checks": checks, "episodes": episodes, "predictions": predictions,
        "totals": totals, "by_split_and_phase": metrics,
        "input_digests": hashes,
        "control_role": "hand_written_harness_controls",
        "learning_demonstrated": False,
    }
