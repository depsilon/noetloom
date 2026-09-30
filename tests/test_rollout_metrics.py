from __future__ import annotations

import copy
import unittest

from noetloom.contracts import ContractError
from noetloom.rollout_metrics import prefix_metrics


def row(actions: list[int], family: str = "demo") -> dict:
    targets = [[(step + bit) % 2 for bit in range(8)] for step in range(len(actions))]
    return {"actions": actions, "targets": targets, "family": family}


def logits_for(targets: list[list[int]], wrong_steps: set[int] | None = None) -> list[list[float]]:
    wrong_steps = wrong_steps or set()
    return [[1.0 if bit != int(step in wrong_steps) else -1.0 for bit in target]
            for step, target in enumerate(targets, start=1)]


class PrefixMetricsTests(unittest.TestCase):
    def test_wrong_then_correct_endpoint_records_recovery_without_full_success(self):
        item = row([0, 1, 2])
        logits = [logits_for(item["targets"], {1})]

        result = prefix_metrics([item], logits)

        all_metrics = result["all"]
        self.assertEqual(all_metrics["first_error_step"], {"1": 1})
        self.assertEqual(all_metrics["exact_prefixes"], 2)
        self.assertEqual(all_metrics["all_prefix_exact"], 0)
        self.assertEqual(all_metrics["final_exact"], 1)
        self.assertEqual(all_metrics["ever_recovered"], 1)
        self.assertEqual(all_metrics["final_recovered"], 1)
        self.assertEqual(all_metrics["prefix_exact_accuracy"], 2 / 3)
        self.assertEqual(all_metrics["all_prefix_exact_accuracy"], 0.0)
        self.assertEqual(all_metrics["final_exact_accuracy"], 1.0)

    def test_correct_then_wrong_is_not_recovery(self):
        item = row([2, 3])
        result = prefix_metrics([item], [logits_for(item["targets"], {2})])

        self.assertEqual(result["all"]["first_error_step"], {"2": 1})
        self.assertEqual(result["all"]["ever_recovered"], 0)
        self.assertEqual(result["all"]["final_recovered"], 0)
        self.assertEqual(result["all"]["final_exact"], 0)
        self.assertEqual(result["all"]["steps"], {"1": {"cases": 1, "exact": 1},
                                                     "2": {"cases": 1, "exact": 0}})

    def test_multiple_recoveries_count_once_per_trajectory(self):
        item = row([0, 1, 2, 3, 0])
        result = prefix_metrics([item], [logits_for(item["targets"], {2, 4})])

        self.assertEqual(result["all"]["exact_prefixes"], 3)
        self.assertEqual(result["all"]["ever_recovered"], 1)
        self.assertEqual(result["all"]["final_recovered"], 1)
        self.assertEqual(result["all"]["first_error_step"], {"2": 1})

    def test_group_support_accumulates_mixed_lengths_and_last_action(self):
        short = row([0, 2], "shared")
        long = row([1, 0, 3], "shared")
        result = prefix_metrics([short, long], [logits_for(short["targets"]),
                                                logits_for(long["targets"], {3})])

        self.assertEqual(result["all"]["cases"], 2)
        self.assertEqual(result["all"]["prefixes"], 5)
        self.assertEqual(result["all"]["steps"], {"1": {"cases": 2, "exact": 2},
                                                    "2": {"cases": 2, "exact": 2},
                                                    "3": {"cases": 1, "exact": 0}})
        self.assertEqual(result["length/2"]["cases"], 1)
        self.assertEqual(result["length/3"]["cases"], 1)
        self.assertEqual(result["action/2"]["cases"], 1)
        self.assertEqual(result["action/3"]["cases"], 1)
        self.assertEqual(result["family/shared"]["cases"], 2)
        self.assertEqual(result["family/shared"]["first_error_step"], {"3": 1, "none": 1})

    def test_zero_logit_predicts_one(self):
        item = {"actions": [0], "targets": [[1] * 8], "family": "zero"}
        result = prefix_metrics([item], [[[0] * 8]])

        self.assertEqual(result["all"]["final_exact"], 1)
        self.assertEqual(result["all"]["first_error_step"], {"none": 1})

    def test_empty_inputs_return_empty_mapping(self):
        self.assertEqual(prefix_metrics([], []), {})

    def test_rejects_malformed_inputs(self):
        good = row([0, 1])
        good_logits = [logits_for(good["targets"])]
        cases = []

        cases.append(([good], []))
        cases.append(([{**good, "actions": []}], [[]]))
        cases.append(([{**good, "actions": [True, 1]}], [good_logits[0]]))
        cases.append(([{**good, "actions": [0, 4]}], [good_logits[0]]))
        cases.append(([{**good, "targets": good["targets"][:1]}], [good_logits[0]]))
        cases.append(([{**good, "targets": [[0] * 7, good["targets"][1]]}], [good_logits[0]]))
        cases.append(([{**good, "targets": [[False] + [0] * 7, good["targets"][1]]}], [good_logits[0]]))
        cases.append(([{**good, "targets": [[2] + [0] * 7, good["targets"][1]]}], [good_logits[0]]))
        cases.append(([{**good, "family": "   "}], [good_logits[0]]))
        cases.append(([good], [[[0] * 8]]))
        cases.append(([good], [[([0] * 7), good_logits[0][1]]]))
        for value in (True, float("nan"), float("inf"), -float("inf"), "0.0", 10 ** 10000):
            bad = copy.deepcopy(good_logits)
            bad[0][0][0] = value
            cases.append(([good], bad))

        for rows, logits in cases:
            with self.subTest(rows=rows, logits_type=type(logits).__name__):
                with self.assertRaises(ContractError):
                    prefix_metrics(rows, logits)

    def test_rejects_non_list_roots(self):
        for rows, logits in ((None, []), ([], None), ({}, {})):
            with self.subTest(rows=rows, logits=logits):
                with self.assertRaises(ContractError):
                    prefix_metrics(rows, logits)


if __name__ == "__main__":
    unittest.main()
