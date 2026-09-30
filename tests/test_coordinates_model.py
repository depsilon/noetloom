import copy
import unittest

from noetloom import state_rep_model
from noetloom.contracts import ContractError
from noetloom.coordinates_model import (
    _coupling, advance, forward_ops, initial_state, parameter_count, scalar_forward,
    shapes, validate_snapshot,
)


def _zeros(shape):
    if len(shape) == 1:
        return [0.0] * shape[0]
    return [_zeros(shape[1:]) for _ in range(shape[0])]


def _snapshot(arm):
    return {"schema_version": "noetloom.coordinates_parameters.v1", "arm": arm,
            "seed": 7, "step": 0,
            "tensors": {name: _zeros(shape) for name, shape in shapes(arm).items()}}


class CoordinatesModelTests(unittest.TestCase):
    def test_parameter_counts_and_operation_counts(self):
        self.assertEqual([parameter_count(a) for a in ("latent", "direct", "reversible")],
                         [1804, 5416, 1780])
        self.assertEqual(forward_ops("reversible", 3),
                         {"multiply": 5100, "add": 5180, "tanh": 480})
        self.assertEqual(forward_ops("latent", 2), state_rep_model.forward_ops("latent", 2))
        self.assertEqual(forward_ops("direct", 2), state_rep_model.forward_ops("direct", 2))

    def test_legacy_arms_preserve_shapes_and_outputs(self):
        for arm in ("latent", "direct"):
            with self.subTest(arm=arm):
                snapshot = _snapshot(arm)
                old = {**snapshot, "schema_version": "noetloom.state_rep_parameters.v1"}
                self.assertEqual(shapes(arm), state_rep_model.shapes(arm))
                self.assertEqual(initial_state(snapshot, [0.2] * 10),
                                 state_rep_model.initial_state(old, [0.2] * 10))
                self.assertEqual(scalar_forward(snapshot, [0.2] * 10, [1, 3]),
                                 state_rep_model.scalar_forward(old, [0.2] * 10, [1, 3]))

    def test_nonzero_coupling_inverts_independently_for_two_masks(self):
        snapshot = _snapshot("reversible")
        tensors = snapshot["tensors"]
        for layer in range(4):
            tensors["coupling_first_weight"][layer][0][0] = 0.7 + layer * 0.1
            tensors["coupling_first_weight"][layer][1][1] = -0.4
            tensors["coupling_first_bias"][layer][2] = 0.13 * (layer + 1)
            tensors["coupling_last_weight"][layer][0][2] = 0.8
            tensors["coupling_last_weight"][layer][2][0] = -0.35
            tensors["coupling_last_bias"][layer][1] = 0.05 * layer
        for values in ([0.1, -0.3, 0.7, 0.2, -0.4, 0.9, 0.15, -0.6, 0.5, 0.35],
                       [-0.8, 0.25, 0.11, -0.45, 0.6, 0.33, -0.2, 0.71, -0.19, 0.04]):
            encoded = _coupling(tensors, list(values), inverse=False)
            decoded = _coupling(tensors, encoded, inverse=True)
            for actual, expected in zip(decoded, values):
                self.assertAlmostEqual(actual, expected, places=13)

    def test_snapshot_rejects_shapes_nonfinite_bool_seed_and_unknown_fields(self):
        bad_shape = _snapshot("reversible")
        bad_shape["tensors"]["coupling_first_weight"][0][0].pop()
        with self.assertRaises(ContractError):
            validate_snapshot(bad_shape)
        bad_value = _snapshot("reversible")
        bad_value["tensors"]["transition_bias"][0][0] = float("inf")
        with self.assertRaises(ContractError):
            validate_snapshot(bad_value)
        bad_seed = _snapshot("latent")
        bad_seed["seed"] = True
        with self.assertRaises(ContractError):
            validate_snapshot(bad_seed)
        extra = _snapshot("direct")
        extra["surprise"] = 1
        with self.assertRaises(ContractError):
            validate_snapshot(extra)


if __name__ == "__main__":
    unittest.main()
