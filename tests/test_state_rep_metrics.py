from __future__ import annotations

import copy
import unittest

from noetloom.contracts import ContractError
from noetloom.state_rep_metrics import continuation_metrics, reconstruction_metrics, score


def vector(value=0.0):
    return [float(value)] * 10


def row(actions, targets=None, family="demo", current=None):
    return {"actions": actions, "targets": targets or [vector() for _ in actions],
            "family": family, "current": vector() if current is None else current}


def continuation_row(suffix, targets=None, family="demo", current=None):
    return {"history_a": "unused-a", "history_b": "unused-b", "suffix": suffix,
            "targets": targets or [vector() for _ in suffix], "family": family,
            "current": vector() if current is None else current}


class StateRepresentationMetricsTests(unittest.TestCase):
    def test_wrong_intermediate_and_recovery_do_not_imply_full_rollout_success(self):
        item = row([0, 1, 2])
        outputs = [[vector(), [0.5] + [0.0] * 9, vector()]]
        result = score([item], outputs, tolerance=0.25)["all"]
        self.assertEqual(result["first_error_step"], {"2": 1})
        self.assertEqual(result["exact_prefixes"], 2)
        self.assertEqual(result["all_prefix_exact"], 0)
        self.assertEqual(result["final_exact"], 1)
        self.assertEqual(result["ever_recovered"], 1)
        self.assertEqual(result["final_recovered"], 1)
        self.assertAlmostEqual(result["mse"], 0.5**2 / 30)

    def test_recovery_counts_once_per_trajectory_and_aggregates_groups(self):
        first = row([0, 1, 2, 3], family="shared")
        second = row([1, 0], family="shared")
        first_outputs = [vector(), [0.4] + [0.0] * 9, vector(), [0.4] + [0.0] * 9]
        result = score([first, second], [first_outputs, [vector(), vector()]], tolerance=0.25)
        self.assertEqual(result["all"]["cases"], 2)
        self.assertEqual(result["all"]["prefixes"], 6)
        self.assertEqual(result["all"]["ever_recovered"], 1)
        self.assertEqual(result["all"]["first_error_step"], {"2": 1, "none": 1})
        self.assertEqual(result["length/4"]["cases"], 1)
        self.assertEqual(result["length/2"]["cases"], 1)
        self.assertEqual(result["action/3"]["cases"], 1)
        self.assertEqual(result["action/0"]["cases"], 1)
        self.assertEqual(result["family/shared"]["cases"], 2)

    def test_tolerance_boundary_and_reconstruction_empty_support(self):
        item = row([2])
        metrics = score([item], [[ [0.25] + [0.0] * 9 ]], tolerance=0.25)["all"]
        self.assertEqual(metrics["final_exact"], 1)
        self.assertEqual(metrics["maximum_absolute_error"], 0.25)
        reconstruction = reconstruction_metrics([vector()], [[0.25] + [0.0] * 9])
        self.assertEqual((reconstruction["cases"], reconstruction["exact"], reconstruction["accuracy"]), (1, 1, 1.0))
        self.assertEqual(reconstruction_metrics([], []), {
            "cases": 0, "exact": 0, "accuracy": None, "mse": None, "maximum_absolute_error": None})

    def test_paired_equal_but_wrong_future_is_agreement_not_correctness(self):
        item = continuation_row([0, 1], current=vector())
        wrong = [[1.0] + [0.0] * 9, vector()]
        metrics = continuation_metrics([item], [wrong], [copy.deepcopy(wrong)], [vector()], [vector()],
                                       [[0.0] * 10], [[0.0] * 10])["all"]
        self.assertEqual(metrics["close_agreement"], 1)
        self.assertEqual(metrics["wrong_close_agreement"], 1)
        self.assertEqual(metrics["both_suffix_exact"], 0)
        self.assertEqual(metrics["current_both_exact"], 1)
        self.assertEqual(metrics["conditional_suffix_exact"], 0)
        self.assertEqual(metrics["conditional_accuracy"], 0.0)
        self.assertEqual(metrics["first_error_step"], {"1": 1})

    def test_distinct_latent_states_with_identical_correct_future_remain_correct(self):
        item = continuation_row([3], family="equivalent")
        future = [[vector()]]
        metrics = continuation_metrics([item], future, copy.deepcopy(future), [vector()], [vector()],
                                       [[1.0] + [0.0] * 9], [[-1.0] + [0.0] * 9])
        self.assertEqual(metrics["all"]["both_suffix_exact"], 1)
        self.assertEqual(metrics["all"]["close_agreement"], 1)
        self.assertEqual(metrics["all"]["wrong_close_agreement"], 0)
        self.assertAlmostEqual(metrics["all"]["mean_squared_state_distance"], 0.4)

    def test_conditional_suffix_accuracy_is_none_without_current_support(self):
        item = continuation_row([0], current=vector())
        wrong_current = [[1.0] + [0.0] * 9]
        metrics = continuation_metrics([item], [[vector()]], [[vector()]], wrong_current, wrong_current,
                                       [vector()], [vector()])["all"]
        self.assertEqual(metrics["current_both_exact"], 0)
        self.assertEqual(metrics["conditional_suffix_exact"], 0)
        self.assertIsNone(metrics["conditional_accuracy"])

    def test_empty_inputs_return_empty_mappings(self):
        self.assertEqual(score([], []), {})
        self.assertEqual(continuation_metrics([], [], [], [], [], [], []), {})

    def test_rejects_malformed_rows_outputs_actions_vectors_and_tolerance(self):
        good = row([0, 1])
        outputs = [[vector(), vector()]]
        invalid_pairs = [
            ([good], []),
            ([{**good, "actions": [True, 1]}], outputs),
            ([{**good, "actions": [0, 4]}], outputs),
            ([{**good, "targets": [vector()]}], outputs),
            ([{**good, "targets": [[False] + [0.0] * 9, vector()]}], outputs),
            ([{**good, "family": "  "}], outputs),
            ([good], [[vector()]]),
            ([good], [[([0.0] * 9), vector()]]),
            ([good], [[ [float("nan")] + [0.0] * 9, vector() ]]),
            ([good], [[ [True] + [0.0] * 9, vector() ]]),
            ([good], [[ [10**10000] + [0.0] * 9, vector() ]]),
        ]
        for rows, predictions in invalid_pairs:
            with self.subTest(rows=rows):
                with self.assertRaises(ContractError):
                    score(rows, predictions)
        with self.assertRaises(ContractError):
            score([good], outputs, tolerance=True)
        with self.assertRaises(ContractError):
            reconstruction_metrics([vector()], [[float("inf")] + [0.0] * 9])
        with self.assertRaises(ContractError):
            reconstruction_metrics([vector()], [], tolerance=0)

    def test_rejects_malformed_continuation_counts_and_values(self):
        item = continuation_row([0, 1])
        good = [[vector(), vector()]]
        currents, states = [vector()], [vector()]
        kwargs = (good, good, currents, currents, states, states)
        malformed = [
            ([item], [], good, currents, currents, states, states),
            ([{**item, "suffix": [0, True]}], good, good, currents, currents, states, states),
            ([{**item, "current": [False] + [0.0] * 9}], good, good, currents, currents, states, states),
            ([item], [[vector()]], good, currents, currents, states, states),
            ([item], good, good, [], currents, states, states),
            ([item], good, good, currents, currents, [[float("nan")] + [0.0] * 9], states),
        ]
        for args in malformed:
            with self.subTest(args=args[:2]):
                with self.assertRaises(ContractError):
                    continuation_metrics(*args)
        with self.assertRaises(ContractError):
            continuation_metrics([item], *kwargs, tolerance=False)

    def test_continuation_accepts_suffix_rows_and_rejects_invalid_suffix(self):
        item = continuation_row([2], family="actual-shape", current=vector())
        result = continuation_metrics([item], [[vector()]], [[vector()]], [vector()], [vector()],
                                      [vector()], [vector()])
        self.assertEqual(result["family/actual-shape"]["both_suffix_exact"], 1)
        self.assertEqual(set(item), {"history_a", "history_b", "suffix", "targets", "family", "current"})
        for invalid_suffix in ([], [True], [4]):
            with self.subTest(suffix=invalid_suffix):
                with self.assertRaises(ContractError):
                    continuation_metrics([{**item, "suffix": invalid_suffix}], [[vector()]], [[vector()]],
                                         [vector()], [vector()], [vector()], [vector()])

    def test_error_aggregate_overflow_is_rejected(self):
        extreme = [1e308] + [0.0] * 9
        opposite = [-1e308] + [0.0] * 9
        with self.assertRaises(ContractError):
            score([row([0], [opposite])], [[extreme]])
        with self.assertRaises(ContractError):
            reconstruction_metrics([opposite], [extreme])
        with self.assertRaises(ContractError):
            score([row([0], [vector()])], [[[1e200] + [0.0] * 9]])
        item = continuation_row([0], [opposite])
        with self.assertRaises(ContractError):
            continuation_metrics([item], [[extreme]], [[extreme]], [vector()], [vector()],
                                 [vector()], [vector()])
        item = continuation_row([0], [vector()])
        with self.assertRaises(ContractError):
            continuation_metrics([item], [[vector()]], [[vector()]], [vector()], [vector()],
                                 [[1e308] + [0.0] * 9], [[-1e308] + [0.0] * 9])
        with self.assertRaises(ContractError):
            continuation_metrics([item], [[vector()]], [[vector()]], [vector()], [vector()],
                                 [[1e200] + [0.0] * 9], [vector()])


if __name__ == "__main__":
    unittest.main()
