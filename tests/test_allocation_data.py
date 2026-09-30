from __future__ import annotations

import copy
import unittest

from helpers import ROOT
from noetloom.allocation_data import generate, key_pools
from noetloom.contracts import read_json
from noetloom.learning_data import key_pools as old_pools, observations_only, query_prefixes, reference_answers


class AllocationDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = read_json(ROOT / "experiments/EXP-0003/protocol.json")
        cls.data = generate(cls.protocol)

    def test_new_splits_exclude_all_parent_keys_and_each_other(self):
        pools = [set(values) for values in key_pools().values()]
        excluded = {key for values in old_pools(872341).values() for key in values}
        self.assertEqual(len(excluded), 5120)
        for index, pool in enumerate(pools):
            self.assertFalse(pool & excluded)
            for other in pools[index + 1:]:
                self.assertFalse(pool & other)
        self.assertEqual(self.data, generate(self.protocol))
        self.assertEqual(len(self.data["observable_stream_sha256"]), 224)
        self.assertEqual(len(set(self.data["observable_stream_sha256"])), 224)

    def test_independent_labels_and_ring_retention_on_new_structures(self):
        for rows in self.data["datasets"].values():
            for row in rows:
                self.assertEqual(reference_answers(row["observations"]), [a["expected"] for a in row["answers"]])
                for prefix in query_prefixes([row]):
                    matching = [event for event in prefix["events"] if event["key"] == prefix["key"]]
                    actual = matching[-1]["input"].index(1.0) if matching else 4
                    self.assertEqual(actual, prefix["expected"], "task demands an evicted association")
                    self.assertLessEqual(len(prefix["events"]), 32)

    def test_interleaving_and_capacity_shifts_are_absent_from_fitting(self):
        first = self.data["datasets"]["test_interleaved"][0]
        self.assertEqual([a["phase"] for a in first["answers"]],
                         ["initial", "initial", "deletion", "revision", "reinsertion", "deletion", "recovery", "unknown"])
        for name in ("train", "validation"):
            phases = {answer["phase"] for row in self.data["datasets"][name] for answer in row["answers"]}
            self.assertNotIn("reinsertion", phases)
            self.assertNotIn("recovery", phases)
        capacity = self.data["datasets"]["test_capacity"][0]
        self.assertEqual(next(i for i, op in enumerate(capacity["observations"]) if op["op"] == "query"), 28)

    def test_scorer_metadata_is_removed_from_runtime_inputs(self):
        rows = self.data["datasets"]["test_interleaved"]
        runtime = observations_only(rows)
        changed = copy.deepcopy(rows)
        for row in changed:
            row["answers"] = [{"injected": "not available to model"}]
        self.assertEqual(runtime, observations_only(changed))
        for row in runtime:
            self.assertEqual(set(row), {"id", "observations"})
            for op in row["observations"]:
                self.assertFalse({"expected", "phase", "answers"} & set(op))


if __name__ == "__main__":
    unittest.main()
