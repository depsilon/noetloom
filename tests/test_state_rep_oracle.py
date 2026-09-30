from __future__ import annotations

import math
import unittest

from noetloom.state_rep_data import observe, path
from noetloom.state_rep_model import parameter_count, scalar_forward, validate_snapshot
from noetloom.state_rep_oracle import oracle_snapshot


class StateRepresentationOracleTests(unittest.TestCase):
    def test_scalar_product_identity_on_all_bipolar_inputs(self):
        alpha = 2.0 / (math.tanh(3.0) - 3.0 * math.tanh(1.0))
        beta = -1.0 - 2.0 * alpha * math.tanh(1.0)
        for u in (-1.0, 1.0):
            for v in (-1.0, 1.0):
                product = alpha * math.tanh(u + v + 1.0) - alpha * math.tanh(u + v - 1.0) + beta
                self.assertAlmostEqual(product, u * v, delta=1e-10)

    def test_snapshot_contract_and_parameter_count(self):
        snapshot = oracle_snapshot(self.config())
        validate_snapshot(snapshot)
        self.assertEqual(snapshot["arm"], "latent")
        self.assertEqual((snapshot["seed"], snapshot["step"]), (0, 0))
        self.assertEqual(parameter_count(snapshot["arm"]), 1804)

    def test_one_and_six_step_paths_match_synthetic_data(self):
        config = self.config()
        model = oracle_snapshot(config)
        for initial, actions in ((37, [2]), (731, [1, 3, 0, 2, 2, 1])):
            with self.subTest(initial=initial, actions=actions):
                outputs, states = scalar_forward(model, observe(config, initial, "nonlinear"), actions)
                expected_states = path(config, initial, actions)[1:]
                self.assertEqual(len(outputs), len(actions))
                for actual_state, expected_state in zip(states, expected_states):
                    for actual, expected in zip(actual_state,
                                                [float(2 * ((expected_state >> bit) & 1) - 1)
                                                 for bit in range(10)]):
                        self.assertAlmostEqual(actual, expected, delta=1e-10)
                for actual, expected_state in zip(outputs, expected_states):
                    expected = observe(config, expected_state, "nonlinear")
                    for value, wanted in zip(actual, expected):
                        self.assertAlmostEqual(value, wanted, delta=1e-10)

    @staticmethod
    def config():
        return {"world_seed": 29, "nonlinear_coefficient": 0.375,
                "nonlinear_shears": [(2, 0, 1)]}


if __name__ == "__main__":
    unittest.main()
