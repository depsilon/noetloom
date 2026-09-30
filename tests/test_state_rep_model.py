from __future__ import annotations

import copy
import math
import unittest

from noetloom.contracts import ContractError
from noetloom.state_rep_model import (
    advance,
    forward_ops,
    initial_state,
    parameter_count,
    scalar_forward,
    shapes,
    validate_snapshot,
)


def zeros(shape: tuple[int, ...]):
    if len(shape) == 1:
        return [0.0] * shape[0]
    return [zeros(shape[1:]) for _ in range(shape[0])]


def snapshot(arm="latent"):
    return {"schema_version": "noetloom.state_rep_parameters.v1", "arm": arm,
            "seed": 17, "step": 11,
            "tensors": {name: zeros(shape) for name, shape in shapes(arm).items()}}


def set_identity(matrix):
    for i in range(min(len(matrix), len(matrix[0]))):
        matrix[i][i] = 1.0


class StateRepresentationModelTests(unittest.TestCase):
    def test_residual_encoder_and_decoder_with_explicit_affine_transition(self):
        model = snapshot()
        tensors = model["tensors"]
        # E(x)[0] = x[0] + 2*tanh(x[0]) + 0.5; D is the identity.
        tensors["encoder_first_weight"][0][0] = 1.0
        tensors["encoder_last_weight"][0][0] = 2.0
        tensors["encoder_last_bias"][0] = 0.5
        set_identity(tensors["transition_weight"][0])
        tensors["transition_weight"][0][0][0] = 0.0
        tensors["transition_weight"][0][0][1] = 1.0
        tensors["transition_weight"][0][1][0] = 1.0
        tensors["transition_weight"][0][1][1] = 0.0
        tensors["transition_bias"][0][0] = 0.25
        tensors["transition_bias"][0][1] = -0.5

        observation = [0.2, -0.4] + [0.0] * 8
        encoded = initial_state(model, observation)
        self.assertAlmostEqual(encoded[0], 0.2 + 2.0 * math.tanh(0.2) + 0.5)
        self.assertAlmostEqual(encoded[1], -0.4)

        outputs, states = scalar_forward(model, observation, [0, 0])
        first = [encoded[1] + 0.25, encoded[0] - 0.5] + [0.0] * 8
        second = [first[1] + 0.25, first[0] - 0.5] + [0.0] * 8
        for actual, expected in zip(states[0], first):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(states[1], second):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(outputs, states)  # zero-residual decoder

    def test_direct_zero_residual_is_identity_for_any_action(self):
        model = snapshot("direct")
        observation = [float(i) / 10 for i in range(10)]
        self.assertEqual(initial_state(model, observation), observation)
        outputs, states = scalar_forward(model, observation, [3, 1])
        self.assertEqual(outputs, [observation, observation])
        self.assertEqual(states, [observation, observation])

    def test_action_order_changes_noncommuting_affine_rollout(self):
        model = snapshot()
        matrices = model["tensors"]["transition_weight"]
        for action in range(4):
            set_identity(matrices[action])
        # A0 adds coordinate 1 into coordinate 0. A1 adds coordinate 0 into 1.
        matrices[0][0][1] = 1.0
        matrices[1][1][0] = 1.0
        initial = [1.0, 2.0] + [0.0] * 8
        forward_outputs, forward_states = scalar_forward(model, initial, [0, 1])
        reverse_outputs, reverse_states = scalar_forward(model, initial, [1, 0])
        self.assertEqual(forward_states[-1][:2], [3.0, 5.0])
        self.assertEqual(reverse_states[-1][:2], [4.0, 3.0])
        self.assertNotEqual(forward_outputs[-1], reverse_outputs[-1])

    def test_snapshot_schema_dimensions_and_finite_numeric_contract(self):
        valid = snapshot()
        validate_snapshot(valid)
        cases = []
        unknown = copy.deepcopy(valid)
        unknown["extra"] = True
        cases.append(unknown)
        wrong_dimension = copy.deepcopy(valid)
        wrong_dimension["tensors"]["transition_bias"][0].pop()
        cases.append(wrong_dimension)
        boolean = copy.deepcopy(valid)
        boolean["tensors"]["encoder_first_weight"][0][0] = True
        cases.append(boolean)
        nan_value = copy.deepcopy(valid)
        nan_value["tensors"]["decoder_last_bias"][0] = float("nan")
        cases.append(nan_value)
        huge_int = copy.deepcopy(valid)
        huge_int["tensors"]["transition_bias"][0][0] = 10**10000
        cases.append(huge_int)
        bad_seed = copy.deepcopy(valid)
        bad_seed["seed"] = True
        cases.append(bad_seed)
        bad_step = copy.deepcopy(valid)
        bad_step["step"] = 4353
        cases.append(bad_step)
        for invalid in cases:
            with self.subTest(invalid=invalid.get("seed", "tensor")):
                with self.assertRaises(ContractError):
                    validate_snapshot(invalid)

    def test_invalid_observation_state_and_action_are_rejected(self):
        model = snapshot()
        with self.assertRaises(ContractError):
            initial_state(model, [0.0] * 9)
        with self.assertRaises(ContractError):
            initial_state(model, [True] + [0.0] * 9)
        with self.assertRaises(ContractError):
            scalar_forward(model, [0.0] * 10, [0, True])
        with self.assertRaises(ContractError):
            advance(model, [0.0] * 10, 4)
        outputs, states = scalar_forward(model, [0.0] * 10, [])
        self.assertEqual((outputs, states), ([], []))

    def test_declared_parameter_and_forward_operation_counts(self):
        self.assertEqual(parameter_count("latent"), 1804)
        self.assertEqual(parameter_count("consistent"), 1804)
        self.assertEqual(parameter_count("direct"), 5416)
        self.assertEqual(forward_ops("latent", 0), {"multiply": 640, "add": 650, "tanh": 32})
        self.assertEqual(forward_ops("consistent", 2), {"multiply": 2120, "add": 2150, "tanh": 96})
        self.assertEqual(forward_ops("direct", 2), {"multiply": 2560, "add": 2580, "tanh": 128})


if __name__ == "__main__":
    unittest.main()
