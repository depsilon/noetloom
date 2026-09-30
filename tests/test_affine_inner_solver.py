"""Independent synthetic checks for the bounded affine identification helper."""
from __future__ import annotations

import unittest

from noetloom.contracts import ContractError

try:
    from noetloom.affine_inner_torch import solve_affine
    import torch
except ImportError:
    solve_affine = None
    torch = None


@unittest.skipIf(torch is None, "optional PyTorch backend is unavailable")
class AffineInnerSolverTests(unittest.TestCase):
    def test_basis_fit_recovers_dense_nonsymmetric_map_and_bias(self):
        initial = torch.cat((torch.zeros((1, 10), dtype=torch.float64),
                             torch.eye(10, dtype=torch.float64),
                             -torch.eye(10, dtype=torch.float64)))
        weight_expected = torch.tensor(
            [[(i * 7 - j * 3 + 2) / 37 for j in range(10)] for i in range(10)],
            dtype=torch.float64,
        )
        bias_expected = torch.linspace(-0.4, 0.5, 10, dtype=torch.float64)
        target = initial @ weight_expected.T + bias_expected
        initial_before, target_before = initial.clone(), target.clone()

        weight, bias, diagnostic = solve_affine(initial, target)

        self.assertTrue(torch.allclose(weight.double(), weight_expected, atol=2e-7, rtol=0))
        self.assertTrue(torch.allclose(bias.double(), bias_expected, atol=2e-7, rtol=0))
        self.assertEqual(tuple(weight.shape), (10, 10))
        self.assertEqual(tuple(bias.shape), (10,))
        self.assertEqual(weight.dtype, torch.float32)
        self.assertEqual(bias.dtype, torch.float32)
        self.assertEqual(diagnostic["rows"], 21)
        self.assertEqual(diagnostic["rank"], 11)
        self.assertEqual(len(diagnostic["singular_values"]), 11)
        self.assertLess(diagnostic["latent_mse_float64"], 1e-25)
        self.assertTrue(torch.equal(initial, initial_before))
        self.assertTrue(torch.equal(target, target_before))

    def test_noisy_overdetermined_fit_is_stationary_and_reports_residual(self):
        rows = torch.arange(80, dtype=torch.float64).unsqueeze(1)
        columns = torch.arange(10, dtype=torch.float64).unsqueeze(0)
        initial = torch.sin(rows * (columns + 1) * 0.017) + torch.cos(rows * 0.071 + columns)
        weight_expected = torch.tensor(
            [[(i - j * 2) / 29 for j in range(10)] for i in range(10)], dtype=torch.float64
        )
        bias_expected = torch.linspace(-0.2, 0.3, 10, dtype=torch.float64)
        noise = 0.01 * torch.sin(rows * 0.19 + columns * 0.43)
        target = initial @ weight_expected.T + bias_expected + noise

        weight, bias, diagnostic = solve_affine(initial, target)

        self.assertLess(diagnostic["latent_mse_float64"], float(noise.square().mean()))
        self.assertLess(diagnostic["normal_residual_ratio"], 1e-12)
        self.assertLessEqual(diagnostic["condition"], 1e8)
        cast_residual = initial @ weight.double().T + bias.double() - target
        self.assertAlmostEqual(diagnostic["latent_mse_float32"], float(cast_residual.square().mean()), places=13)

    def test_rank_deficiency_and_malformed_inputs_are_rejected(self):
        rows = torch.arange(30, dtype=torch.float64).unsqueeze(1)
        columns = torch.arange(10, dtype=torch.float64).unsqueeze(0)
        base = torch.sin(rows * (columns + 1) * 0.037) + torch.cos(rows * 0.13 + columns)
        target = base.clone()
        deficient = base.clone()
        deficient[:, 1] = deficient[:, 0]
        with self.assertRaises(ContractError):
            solve_affine(deficient, target)
        with self.assertRaises(ContractError):
            solve_affine(base[:10], target[:10])
        with self.assertRaises(ContractError):
            solve_affine(base, target[:, :9])
        bad = base.clone()
        bad[0, 0] = float("nan")
        with self.assertRaises(ContractError):
            solve_affine(bad, target)
        with self.assertRaises(ContractError):
            solve_affine(base.float(), target)
        with self.assertRaises(ContractError):
            solve_affine(base, target, rcond=1.0)
        with self.assertRaises(ContractError):
            solve_affine(base, target, max_condition=0.5)

    def test_full_rank_but_excess_condition_is_rejected(self):
        basis = torch.cat((torch.zeros((1, 10), dtype=torch.float64),
                           torch.eye(10, dtype=torch.float64), -torch.eye(10, dtype=torch.float64)))
        basis[:, 0] *= 1e-9
        with self.assertRaisesRegex(ContractError, "max_condition"):
            solve_affine(basis, basis)


if __name__ == "__main__":
    unittest.main()
