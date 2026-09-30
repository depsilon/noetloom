from __future__ import annotations

import json
import math
from pathlib import Path
import unittest

from noetloom.state_rep_data import (
    acquisition_raw,
    audit,
    continuation_raw,
    continuations,
    development,
    development_raw,
    generate,
    observe,
    pairs_in,
    partition,
    path,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((ROOT / "experiments/EXP-0007/protocol.json").read_text())


class StateRepresentationDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = PROTOCOL
        # Each full finite input audit takes a couple of seconds; cache its result for
        # assertions below rather than rebuilding the same audit in separate tests.
        cls.audits = {name: audit(cls.protocol, name) for name in cls.protocol["observations"]}

    def assert_rendered_row(self, item: dict):
        self.assertEqual(set(item), {"initial", "actions", "targets", "family"})
        self.assertTrue(item["family"])
        self.assertTrue(item["actions"])
        self.assertEqual(len(item["initial"]), 10)
        self.assertEqual(len(item["targets"]), len(item["actions"]))
        self.assertTrue(all(type(action) is int and 0 <= action < 4 for action in item["actions"]))
        for vector in [item["initial"], *item["targets"]]:
            self.assertEqual(len(vector), 10)
            self.assertTrue(all(type(value) is float and math.isfinite(value) for value in vector))

    def test_complement_paired_partitions_are_disjoint_and_cover_world(self):
        parts = partition(self.protocol["data"])

        self.assertEqual({name: len(states) for name, states in parts.items()},
                         {"training": 512, "validation": 128, "development": 192, "final": 192})
        sets = {name: set(states) for name, states in parts.items()}
        self.assertTrue(all(sets[left].isdisjoint(sets[right])
                            for i, left in enumerate(parts)
                            for right in list(parts)[i + 1:]))
        self.assertEqual(set.union(*sets.values()), set(range(1024)))
        for states in parts.values():
            self.assertEqual(len(states), len(set(states)))
            self.assertTrue(all((state ^ 1023) in states for state in states))

    def test_nonlinear_shears_are_invertible_by_subtracting_original_sources(self):
        config = self.protocol["data"]
        coefficient = config["nonlinear_coefficient"]
        for state in range(1024):
            canonical = observe(config, state, "aligned")
            nonlinear = observe(config, state, "nonlinear")
            recovered = nonlinear[:]
            for target, source_a, source_b in config["nonlinear_shears"]:
                recovered[target] -= coefficient * canonical[source_a] * canonical[source_b]
            self.assertEqual(recovered, canonical, f"state {state}")

    def test_actual_paths_respect_training_and_heldout_state_partitions(self):
        config = self.protocol["data"]
        parts = partition(config)
        train = set(parts["training"])

        for stage in ("tiny", "one", "mixed"):
            training_rows = acquisition_raw(self.protocol, stage)["training"]
            for initial, actions, _family in training_rows:
                self.assertTrue(set(path(config, initial, actions)) <= train,
                                f"{stage} training path left training states")

        for stage in ("one", "mixed"):
            for initial, actions, _family in acquisition_raw(self.protocol, stage)["validation"]:
                self.assertTrue(set(path(config, initial, actions)) <= train | set(parts["validation"]))
        for initial, actions, _family in development_raw(self.protocol):
            self.assertTrue(set(path(config, initial, actions)) <= train | set(parts["development"]))

    def test_rendered_rows_have_only_observation_inputs_and_expected_shapes(self):
        for observation in ("aligned", "nonlinear"):
            for stage, expected in (("tiny", (32, 0)), ("one", (512, 128)), ("mixed", (768, 256))):
                rendered = generate(self.protocol, observation, stage)
                self.assertEqual((len(rendered["training"]), len(rendered["validation"])), expected)
                for rows in rendered.values():
                    for item in rows:
                        self.assert_rendered_row(item)
            dev = development(self.protocol, observation)
            self.assertTrue(dev)
            for item in dev:
                self.assert_rendered_row(item)

    def test_common_state_continuations_have_distinct_histories_and_no_final_pairs(self):
        config = self.protocol["data"]
        final_pairs = {tuple(pair) for pair in config["final_pairs"]}
        raw = continuation_raw(self.protocol)

        self.assertEqual(len(raw), 64)
        self.assertEqual(len({item["state"] for item in raw}), 64)
        for item in raw:
            state = item["state"]
            start_a, actions_a = item["history_a"]
            start_b, actions_b = item["history_b"]
            self.assertEqual((len(actions_a), len(actions_b)), (2, 3))
            self.assertNotEqual(actions_a, actions_b)
            self.assertEqual(path(config, start_a, actions_a)[-1], state)
            self.assertEqual(path(config, start_b, actions_b)[-1], state)
            self.assertFalse(pairs_in(actions_a + item["suffix"]) & final_pairs)
            self.assertFalse(pairs_in(actions_b + item["suffix"]) & final_pairs)

        for observation in ("aligned", "nonlinear"):
            rendered = continuations(self.protocol, observation)
            self.assertEqual(len(rendered), 64)
            for raw_item, item in zip(raw, rendered):
                self.assertEqual(set(item), {"history_a", "history_b", "current", "suffix", "targets", "family"})
                self.assertEqual(len(item["current"]), 10)
                self.assertEqual(len(item["suffix"]), len(item["targets"]))
                self.assertTrue(all(type(action) is int and 0 <= action < 4 for action in item["suffix"]))
                self.assertTrue(all(len(target) == 10 and all(type(value) is float and math.isfinite(value)
                                                                for value in target) for target in item["targets"]))
                self.assertEqual(item["current"], observe(config, raw_item["state"], observation))
                self.assertEqual(item["targets"], [observe(config, state, observation)
                                                    for state in path(config, raw_item["state"], raw_item["suffix"])[1:]])
                for name in ("history_a", "history_b"):
                    history = item[name]
                    self.assertNotIn("state", history)
                    self.assertNotIn("rule", history)
                    self.assert_rendered_row(history)

    def test_actual_input_audits_are_separated_and_have_structural_support(self):
        for observation, report in self.audits.items():
            self.assertEqual(report["training_auxiliary_heldout_state_overlap"], 0)
            audit_input = report["input_prefix_audit"]
            self.assertEqual(audit_input["conflicting_signatures"], 0)
            self.assertTrue(all(not overlap["distinct_signatures"]
                                for overlap in audit_input["overlap"].values()), observation)
            self.assertTrue(all(group["cases"] > 0 for group in audit_input["groups"].values()))
            structural = report["structural_word_counts"]
            self.assertTrue(all(count > 0 for split in structural.values()
                                for count in split.values()), observation)


if __name__ == "__main__":
    unittest.main()
