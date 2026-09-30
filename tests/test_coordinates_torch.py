"""Optional numerical integration checks using the admitted tensor dependency."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noetloom.contracts import ContractError, canonical_bytes, read_json

try:
    from noetloom import coordinates_torch as engine
except ImportError:
    engine = None


@unittest.skipIf(engine is None, "admitted optional PyTorch backend is not on this interpreter's path")
class CoordinateTensorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine.torch.set_num_threads(1)
        cls.protocol = read_json(Path(__file__).resolve().parents[1] / "experiments/EXP-0008/protocol.json")

    def test_initialization_matches_legacy_and_all_reconstruct_identity(self):
        from noetloom.state_rep_torch import Model as Legacy
        torch = engine.torch
        for arm in ("latent", "direct"):
            candidate, previous = engine.Model(arm, 17), Legacy(arm, 17)
            self.assertEqual(candidate.snapshot(0)["tensors"], previous.snapshot(0)["tensors"])
        independent, reversible = engine.Model("latent", 17), engine.Model("reversible", 17)
        self.assertTrue(torch.equal(independent.transition_weight, reversible.transition_weight))
        observations = torch.arange(60, dtype=torch.float32).reshape(2, 3, 10) / 13 - 2
        for arm in self.protocol["arms"]:
            model = engine.Model(arm, 17)
            self.assertTrue(torch.equal(model.decode(model.encode(observations)), observations))

    def test_nonzero_reversible_maps_invert_and_match_scalar_equations(self):
        from noetloom.coordinates_worker import Work, scalar_check
        from noetloom.state_rep_worker import NativeRunner
        torch, model = engine.torch, engine.Model("reversible", 21)
        with torch.no_grad():
            model.coupling_last_weight.uniform_(-0.2, 0.2)
            model.coupling_last_bias.uniform_(-0.2, 0.2)
        observations = torch.arange(80, dtype=torch.float32).reshape(8, 10) / 17 - 2
        recovered = model.decode(model.encode(observations))
        self.assertLess(float((recovered - observations).abs().max().detach()), 2e-6)
        rows = [{"initial": observation, "actions": [0, 2, 1, 3]} for observation in observations.tolist()]
        self.assertLess(scalar_check(NativeRunner(engine, model, Work(self.protocol)), rows, 8)["maximum_absolute_error"], 2e-5)

    def test_prediction_interventions_are_replayed_and_do_not_change_model(self):
        from noetloom.coordinates_worker import Work, perturbations
        from noetloom.state_rep_worker import synthetic
        rows = synthetic()
        for arm in self.protocol["arms"]:
            model, work = engine.Model(arm, 23), Work(self.protocol)
            before = copy.deepcopy(model.snapshot(0))
            result = perturbations(engine, model, rows, 0.01, self.protocol, work)
            self.assertEqual(before, model.snapshot(0))
            self.assertEqual(result, perturbations(engine, model, rows, 0.01, self.protocol, Work(self.protocol)))
            expected = len(self.protocol["diagnostics"]["prediction_perturbation"]["groups"][arm])
            self.assertEqual(work.counts["updates"], expected)
            self.assertEqual(work.counts["probe_updates"], expected)
            if arm == "latent":
                self.assertGreater(result["groups"]["encoder"]["reconstruction_mse_delta"], 0)
                self.assertGreater(result["groups"]["decoder"]["reconstruction_mse_delta"], 0)
            if arm == "reversible":
                self.assertLess(result["groups"]["all"]["after"]["reconstruction"]["maximum_absolute_error"], 2e-6)

    def test_synthetic_fit_full_curve_replay_and_prediction_tamper(self):
        from noetloom import coordinates_worker as worker
        from noetloom.state_rep_worker import synthetic
        protocol = copy.deepcopy(self.protocol)
        protocol["training"]["steps"]["one"] = 16
        protocol["training"]["measurement_steps"]["one"] = [0, 8, 16]
        protocol["diagnostics"]["prediction_perturbation"]["steps"]["one"] = [0, 16]
        dataset = {"training": synthetic(), "validation": synthetic()}
        request = {"kind": "fit", "stage": "one", "arm": "reversible", "seed": 17, "condition": "lr003"}
        with tempfile.TemporaryDirectory() as folder, patch.object(worker.data, "generate", return_value=dataset):
            original, replay = Path(folder) / "fit", Path(folder) / "replay"
            original.mkdir()
            replay.mkdir()
            for directory in (original, replay):
                (directory / "protocol.json").write_bytes(canonical_bytes(protocol))
            (original / "request.json").write_bytes(canonical_bytes(request))
            worker.fit(engine, protocol, request, original, worker.Work(protocol))
            self.assertEqual(read_json(original / "fitting-status.json")["status"], "completed")
            result = worker.verify_fit(engine, protocol, original, replay, worker.Work(protocol))
            self.assertTrue(result["complete_measurement_selection_prediction_perturbation_replay"])
            predictions = read_json(original / "predictions.json")
            predictions["validation"][0][0][0] += 0.1
            (original / "predictions.json").write_bytes(canonical_bytes(predictions))
            with self.assertRaisesRegex(ContractError, "predictions or perturbations"):
                worker.verify_fit(engine, protocol, original, replay, worker.Work(protocol))


if __name__ == "__main__":
    unittest.main()
