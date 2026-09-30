from copy import deepcopy
from pathlib import Path
import unittest

from noetloom.contracts import read_json
from noetloom.learning_data import (episode, generate, key_pools, observations_only,
                                    query_prefixes, reference_answers)

ROOT = Path(__file__).resolve().parents[1]


class LearningDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = read_json(ROOT / "experiments/EXP-0002/protocol.json")
        cls.data = generate(cls.protocol)

    def test_exact_reference_and_split_separation(self):
        pools = key_pools(self.protocol["data"]["generator_seed"])
        self.assertEqual(len(set().union(*(set(pool) for pool in pools.values()))),
                         sum(map(len, pools.values())))
        for name, rows in self.data["datasets"].items():
            for row in rows:
                self.assertEqual([x["expected"] for x in row["answers"]],
                                 reference_answers(row["observations"]))
                self.assertEqual(len(row["answers"]), 8)
                self.assertEqual(len(query_prefixes([row])), 8)
        self.assertEqual(self.data, generate(self.protocol))

    def test_runtime_input_has_no_labels_or_phase_and_prefix_is_causal(self):
        row = self.data["datasets"]["train"][0]
        runtime = observations_only([row])[0]
        self.assertEqual(set(runtime), {"id", "observations"})
        for operation in runtime["observations"]:
            self.assertNotIn("expected", operation)
            self.assertNotIn("phase", operation)
        altered = deepcopy(row)
        altered["answers"][0]["expected"] = 99
        self.assertEqual(observations_only([altered]), [runtime])
        views = query_prefixes([row])
        self.assertEqual(len(views[0]["events"]), 4)
        self.assertEqual(len(views[2]["events"]), 6)
        self.assertEqual(len(views[-1]["events"]), 9)
        self.assertTrue(all(event["written_at"] <= view["writes"]
                            for view in views for event in view["events"]))

    def test_held_out_composition_has_reinsertion_and_recovery(self):
        phases = {answer["phase"] for row in self.data["datasets"]["train"]
                  for answer in row["answers"]}
        self.assertNotIn("reinsertion", phases)
        self.assertNotIn("recovery", phases)
        row = self.data["datasets"]["test_composition"][0]
        answers = {answer["phase"]: answer["expected"] for answer in row["answers"]}
        self.assertEqual(answers["deletion"], 4)
        self.assertLess(answers["reinsertion"], 4)
        self.assertNotEqual(answers["initial"], answers["revision"])
        self.assertEqual(answers["initial"], answers["recovery"])

    def test_manual_operation_semantics_and_prefix_capacity(self):
        key = [1.0] * 16
        ops = [{"op": "write", "key": key, "value": 1},
               {"op": "query", "key": key},
               {"op": "write", "key": key, "value": 3},
               {"op": "query", "key": key}, {"op": "delete", "key": key},
               {"op": "query", "key": key}]
        self.assertEqual(reference_answers(ops), [1, 3, 4])
        row = {"id": "manual", "observations": [
            *({"op": "write", "key": key, "value": 0} for _ in range(40)),
            {"op": "query", "key": key, "query_id": 0}],
            "answers": [{"query_id": 0, "expected": 0}]}
        view = query_prefixes([row])[0]
        self.assertEqual(len(view["events"]), 32)
        self.assertEqual(view["events"][0]["written_at"], 9)
        with self.assertRaises(ValueError):
            episode(list(range(100)), 1, "unregistered", "bad")


if __name__ == "__main__":
    unittest.main()
