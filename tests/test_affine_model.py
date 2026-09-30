import unittest

from noetloom.affine_model import fit_affine, rollout, solve, validate_parameters, vector
from noetloom.contracts import ContractError


class AffineModelTests(unittest.TestCase):
    def test_observed_examples_recover_affine_maps_and_continuous_composition(self):
        states = [[x, y] for x in (-1.0, 1.0) for y in (-1.0, 1.0)]
        examples = []
        for state in states:
            x, y = state
            examples.extend([{"input": state, "action": 0, "target": [2 * y + 0.5, -x]},
                             {"input": state, "action": 1, "target": [x + y, y - 0.25]}])
        parameters, report = fit_affine(examples, actions=2)
        self.assertEqual(report["examples"], 8)
        self.assertEqual([r["rank"] for r in report["actions"]], [3, 3])
        # The second input is the model's non-binary continuous output, not a label.
        self.assertEqual(rollout(parameters, [1, -1], [0, 1]), [[-1.5, -1.0], [-2.5, -1.25]])
        self.assertEqual(rollout(parameters, [1, -1], []), [])

    def test_rank_deficiency_does_not_silently_add_regularization(self):
        rows = [{"input": [1, 1], "action": 0, "target": [0, 0]}] * 3
        with self.assertRaisesRegex(ContractError, "rank deficient"):
            fit_affine(rows, actions=1)

    def test_solver_pivots_and_finite_input(self):
        values, _ = solve([[0, 2], [1, 0]], [[4], [3]])
        self.assertEqual(values, [[3.0], [2.0]])
        with self.assertRaises(ContractError):
            solve([[float('nan')]], [[1]])

    def test_world_metadata_is_refused_at_learning_boundary(self):
        examples = [{"input": [0], "action": 0, "target": [0], "world": [1]},
                    {"input": [1], "action": 0, "target": [1]}]
        with self.assertRaises(ContractError):
            fit_affine(examples, actions=1)

    def test_malformed_observations_and_snapshots_fail_as_contract_errors(self):
        for examples in ([{}], [None], None):
            with self.assertRaises(ContractError):
                fit_affine(examples, actions=1)
        for values in ([True], [10**400], [float('inf')]):
            with self.assertRaises(ContractError):
                vector(values)
        with self.assertRaises(ContractError):
            validate_parameters({"schema_version": "noetloom.affine_parameters.v1", "width": 1,
                                 "actions": [{"weight": None, "bias": [0]}]})


if __name__ == '__main__':
    unittest.main()
