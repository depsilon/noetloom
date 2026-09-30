from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from noetloom.affine_model import fit_affine
from noetloom.contracts import ContractError, read_json
from noetloom.state_rep_worker import AffineRunner, Work, continuation, mean_prediction_loss, persist_check

ROOT = Path(__file__).resolve().parents[1]


class StateRepresentationWorkerTests(unittest.TestCase):
    def setUp(self):
        self.protocol = read_json(ROOT / "experiments/EXP-0007/protocol.json")

    def test_work_charges_auxiliary_mappings_and_blocks_each_registered_limit(self):
        work = Work(self.protocol)
        work.forward("latent", [2, 3])
        work.auxiliary("latent", 7)
        work.auxiliary("consistent", 5, 1)
        self.assertEqual(work.counts["presentations"], 2)
        self.assertEqual(work.counts["forward_prefixes"], 5)
        self.assertEqual(work.counts["auxiliary_observations"], 12)
        self.assertEqual(work.counts["dense_forward_ops"]["multiply"], 2 * 640 + 5 * 740 + 19 * 640)
        for key, ceiling in (("updates", "max_updates_per_run"), ("presentations", "max_presentations_per_run"),
                             ("forward_prefixes", "max_forward_prefixes_per_run"), ("auxiliary_observations", "max_auxiliary_observations_per_run"),
                             ("affine_fit_examples", "max_affine_fit_examples_per_run")):
            with self.subTest(key=key), self.assertRaises(ContractError):
                Work(self.protocol).add(key, self.protocol["budget"][ceiling] + 1)

    def test_prediction_loss_weights_trajectories_equally(self):
        rows = [{"actions": [0], "targets": [[0.0] * 10]}, {"actions": [0, 1], "targets": [[0.0] * 10] * 2}]
        self.assertEqual(mean_prediction_loss(rows, [[[2.0] * 10], [[0.0] * 10, [0.0] * 10]]), 2.0)

    def test_affine_equivalence_survives_invertible_linear_coordinates_and_saved_state(self):
        # An unrelated synthetic system: a linear coordinate change is an implementation
        # check, never evidence that nonlinear state representation was learned.
        def encode(values):
            result = values[:]
            for i in range(1, 10):
                result[i] += 0.25 * result[i - 1]
            return result

        def step(values, action):
            return [(-1 if (i + action) % 3 == 0 else 1) * values[(i + action + 1) % 10] + 0.125 * action for i in range(10)]

        basis = [[0.0] * 10] + [[float(int(i == j)) * sign for i in range(10)] for j in range(10) for sign in (-1, 1)]
        examples = [{"input": encode(value), "action": action, "target": encode(step(value, action))}
                    for value in basis for action in range(4)]
        parameters, _ = fit_affine(examples, actions=4)
        rows = []
        for initial in basis[1:9]:
            targets, current = [], initial
            for action in (0, 2, 1, 3):
                current = step(current, action)
                targets.append(encode(current))
            rows.append({"initial": encode(initial), "actions": [0, 2, 1, 3], "targets": targets, "family": "synthetic"})
        runner = AffineRunner(parameters, Work(self.protocol))
        outputs, _ = runner.infer(rows)
        self.assertLess(mean_prediction_loss(rows, outputs), 1e-24)
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            from noetloom.contracts import canonical_bytes
            (directory / "protocol.json").write_bytes(canonical_bytes(self.protocol))
            self.assertTrue(persist_check(runner, rows, directory, "state.json")["exact_saved_state_continuation"])

    def test_own_continuation_uses_predicted_state_and_control_resets_are_explicit(self):
        class Spy:
            def __init__(self):
                self.starts = []

            def infer(self, histories):
                # Deliberately wrong learned current state, distinct from the true current.
                return ([[[2.0] * 10] for _ in histories], [[[3.0] * 10] for _ in histories])

            def encode(self, observations):
                return [[value + 10 for value in row] for row in observations]

            def resume(self, starts, words):
                self.starts.append(copy.deepcopy(starts))
                return [[state[:] for _ in word] for state, word in zip(starts, words)]

        rows = [{"history_a": {}, "history_b": {}, "current": [1.0] * 10,
                 "suffix": [0, 1], "targets": [[3.0] * 10, [3.0] * 10], "family": "synthetic"}]
        for mode, expected in (("own", 3.0), ("zero_state_after_history", 0.0), ("provided_current_observation_reset_diagnostic", 11.0)):
            runner = Spy()
            result, _ = continuation(runner, rows, mode)
            self.assertEqual(runner.starts, [[[expected] * 10], [[expected] * 10]])
            self.assertEqual(result["scored"]["all"]["current_both_exact"], 0)
            self.assertIsNone(result["scored"]["all"]["conditional_accuracy"])
            self.assertEqual(result["scored"]["all"]["both_suffix_exact"], int(mode == "own"))


if __name__ == "__main__":
    unittest.main()
