"""Synthetic EXP-0010 initialization, fit replay and selection checks."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch

from noetloom import affine_coordinates_worker as affine
from noetloom import representation_bridge_worker as worker
from noetloom.contracts import ContractError, canonical_bytes, read_json
from noetloom.storage import file_digest

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "experiments/EXP-0010/protocol.json"

try:
    from noetloom import coordinates_torch as engine
except ImportError:
    engine = None


def protocol_fixture():
    protocol = read_json(PROTOCOL_PATH)
    protocol["training"]["steps"]["one"] = 32
    protocol["training"]["measurement_steps"]["one"] = [0, 32]
    protocol["solver"].update(interval=32, training_pairs=84, per_action_pairs=21)
    return protocol


def write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_bytes(value))


def measure_record(step: int, loss: float, accuracy: float) -> dict:
    groups = {"all": {"cases": 4, "all_prefix_exact_accuracy": accuracy},
              "length/1": {"cases": 4, "all_prefix_exact_accuracy": accuracy}}
    groups.update({f"action/{action}": {"cases": 1, "all_prefix_exact_accuracy": accuracy}
                   for action in range(4)})
    split = {"loss": loss, "scored": groups, "reconstruction": {"accuracy": 1.0}}
    return {"step": step, "training": copy.deepcopy(split), "validation": copy.deepcopy(split)}


class WorkerSelectionTests(unittest.TestCase):
    def test_earliest_passing_checkpoint_wins_even_with_later_lower_loss(self):
        protocol = protocol_fixture()
        measurements = [measure_record(64, 0.05, 1.0), measure_record(32, 0.5, 1.0)]
        selected, gate = worker.select_measurement(protocol, "one", measurements)
        self.assertTrue(gate["passed"])
        self.assertEqual(selected, 1)

    def test_no_pass_selects_minimum_validation_loss_with_earliest_tie(self):
        protocol = protocol_fixture()
        measurements = [measure_record(64, 0.5, 0.2), measure_record(32, 0.5, 0.2),
                        measure_record(96, 0.7, 0.2)]
        selected, gate = worker.select_measurement(protocol, "one", measurements)
        self.assertFalse(gate["passed"])
        self.assertEqual(selected, 1)


@unittest.skipIf(engine is None, "optional PyTorch backend is unavailable")
class RepresentationBridgeWorkerTorchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine.torch.set_num_threads(1)

    def setUp(self):
        self.protocol = protocol_fixture()
        self.parent_seed = 13003
        self.adaptation_seed = 14003
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.parent = self.root / "synthetic-retained-parent"
        self.parent.mkdir()
        self.snapshot = engine.Model("reversible", self.parent_seed).snapshot(512)
        # Use distinct, finite synthetic mapping/operation values so every copy
        # boundary can be checked without loading a historical model artifact.
        for name, tensor in self.snapshot["tensors"].items():
            if name == "transition_weight":
                self.snapshot["tensors"][name] = (engine.torch.eye(10).expand(4, -1, -1) * 1.15).tolist()
            elif name == "transition_bias":
                self.snapshot["tensors"][name] = (engine.torch.ones((4, 10)) * 0.13).tolist()
            else:
                value = 0.017 if "weight" in name else -0.023
                self.snapshot["tensors"][name] = (engine.torch.ones_like(engine.torch.tensor(tensor)) * value).tolist()
        self.parent_snapshot = self.parent / "parameters-parent.json"
        self.parent_manifest = self.parent / "manifest.json"
        write_json(self.parent_snapshot, self.snapshot)
        write_json(self.parent_manifest, {"status": "passed", "synthetic": True})
        self.protocol["parents"] = [{
            "seed": self.adaptation_seed,
            "parent_seed": self.parent_seed,
            "run": self.parent.name,
            "manifest_sha256": file_digest(self.parent_manifest),
            "snapshot": self.parent_snapshot.name,
            "snapshot_sha256": file_digest(self.parent_snapshot),
            "evaluation_manifest_sha256": "0" * 64,
        }]
        self.rows = affine.synthetic()
        self.dataset = {"training": self.rows, "validation": copy.deepcopy(self.rows)}

    def _request(self, arm: str) -> dict:
        return {"kind": "fit", "stage": "one", "observation": "shift", "arm": arm,
                "condition": "lr010", "seed": self.adaptation_seed,
                "retained_parent": str(self.parent),
                "retained_parent_manifest_sha256": file_digest(self.parent_manifest)}

    def _directory(self, name: str, arm: str) -> tuple[Path, Path, dict]:
        original = self.root / name
        replay = self.root / (name + "-replay")
        original.mkdir()
        replay.mkdir()
        request = self._request(arm)
        write_json(original / "protocol.json", self.protocol)
        write_json(replay / "protocol.json", self.protocol)
        write_json(original / "request.json", request)
        return original, replay, request

    def _fake_generated_rows(self):
        return self.dataset

    def _fit(self, name: str, arm: str):
        original, replay, request = self._directory(name, arm)
        with patch.object(worker.data, "generate", side_effect=lambda *args: self._fake_generated_rows()):
            worker.fit(engine, self.protocol, request, original, worker.Work(self.protocol))
            result = worker.verify_fit(engine, self.protocol, original, replay, worker.Work(self.protocol))
        return original, replay, request, result

    def test_all_four_initializations_separate_warm_reset_and_frozen_refit_maps(self):
        own = engine.Model("reversible", self.adaptation_seed).snapshot(0)
        for arm in ("frozen_warm", "frozen_reset", "refit_warm", "refit_reset"):
            with self.subTest(arm=arm):
                directory = self.root / ("init-" + arm)
                directory.mkdir()
                write_json(directory / "protocol.json", self.protocol)
                request = self._request(arm)
                initial = worker.initial_snapshot(engine, self.protocol, directory, request)
                self.assertEqual(file_digest(directory / "retained-parameters.json"),
                                 self.protocol["parents"][0]["snapshot_sha256"])
                actual_retained = read_json(directory / "retained-parameters.json")
                self.assertEqual(actual_retained, self.snapshot)
                warm = arm.endswith("_warm")
                frozen = arm.startswith("frozen_")
                for name in initial["tensors"]:
                    expected = self.snapshot["tensors"][name] if (
                        (name.startswith("transition_") and frozen)
                        or (not name.startswith("transition_") and warm)) else own["tensors"][name]
                    self.assertEqual(initial["tensors"][name], expected, f"{arm}/{name}")

    def test_retained_parent_with_changed_snapshot_bytes_is_rejected(self):
        directory = self.root / "bad-parent"
        directory.mkdir()
        write_json(directory / "protocol.json", self.protocol)
        request = self._request("frozen_warm")
        self.parent_snapshot.write_bytes(self.parent_snapshot.read_bytes() + b" ")
        with self.assertRaises(ContractError):
            worker.initial_snapshot(engine, self.protocol, directory, request)

    def test_baseline_and_development_replay_use_restored_bytes_and_embedded_parent(self):
        from contextlib import ExitStack

        rows = copy.deepcopy(self.rows[:4])
        rows[0]["actions"] = [0, 1]
        rows[0]["targets"] *= 2
        pairs = [{"history_a": rows[1], "history_b": rows[2], "current": rows[1]["targets"][-1],
                  "suffix": [0], "targets": rows[3]["targets"], "family": "synthetic"}]
        with ExitStack() as stack:
            stack.enter_context(patch.object(worker.data, "generate", return_value=self.dataset))
            stack.enter_context(patch.object(worker.data, "development", return_value=rows))
            stack.enter_context(patch.object(worker.data, "continuations", return_value=pairs))
            stack.enter_context(patch.object(worker.old_data, "audit", return_value={"reverse_order_sensitivity": {}}))
            baseline_dir = self.root / "baseline"
            baseline_dir.mkdir()
            write_json(baseline_dir / "protocol.json", self.protocol)
            baseline_request = {**self._request("frozen_warm"), "kind": "baseline"}
            write_json(baseline_dir / "request.json", baseline_request)
            worker.baseline(engine, self.protocol, baseline_request, baseline_dir, worker.Work(self.protocol))
            write_json(baseline_dir / "manifest.json", {"fixture": "baseline"})
            baseline_digest = file_digest(baseline_dir / "manifest.json")

            mixed = self.root / "mixed"
            mixed.mkdir()
            write_json(mixed / "protocol.json", self.protocol)
            request = {**self._request("frozen_warm"), "stage": "mixed"}
            write_json(mixed / "request.json", request)
            write_json(mixed / "retained-parameters.json", self.snapshot)
            snapshot = copy.deepcopy(self.snapshot)
            snapshot.update(seed=self.adaptation_seed, step=32)
            write_json(mixed / "parameters-32.json", snapshot)
            write_json(mixed / "fit.json", {**request, "selected_step": 32, "acquisition": {"passed": True}})
            write_json(mixed / "manifest.json", {"fixture": "mixed"})
            evaluation = self.root / "evaluation"
            evaluation.mkdir()
            write_json(evaluation / "protocol.json", self.protocol)
            evaluation_request = {"kind": "evaluate", "original": str(mixed),
                                  "original_manifest_sha256": file_digest(mixed / "manifest.json")}
            write_json(evaluation / "request.json", evaluation_request)
            worker.evaluate(engine, self.protocol, evaluation_request, evaluation, worker.Work(self.protocol))
            write_json(evaluation / "manifest.json", {"fixture": "evaluation"})
            evaluation_digest = file_digest(evaluation / "manifest.json")

            restored = self.root / "restored"
            restored.mkdir()
            for directory in (mixed, evaluation, baseline_dir):
                shutil.copytree(directory, restored / directory.name)
            # Disturb the live copies and remove the external parent. Recovery must
            # still succeed using the restored original, sibling dependency and embed.
            shutil.rmtree(self.parent)
            (mixed / "manifest.json").write_text("{}")
            (evaluation / "result.json").write_text("{}")
            (baseline_dir / "result.json").write_text("{}")
            for name, digest in (("baseline", baseline_digest), ("evaluation", evaluation_digest)):
                output = self.root / ("replay-" + name)
                output.mkdir()
                write_json(output / "protocol.json", self.protocol)
                worker.replay(engine, self.protocol, {"original": str(restored / name),
                              "original_manifest_sha256": digest}, output, worker.Work(self.protocol))
                self.assertEqual(read_json(output / "result.json"), read_json(restored / name / "result.json"))

    def test_four_32_update_synthetic_fits_replay_and_charge_expected_work(self):
        for arm in ("frozen_warm", "frozen_reset", "refit_warm", "refit_reset"):
            with self.subTest(arm=arm):
                original, _replay, _request, result = self._fit("fit-" + arm, arm)
                record = read_json(original / "fit.json")
                self.assertEqual(read_json(original / "fitting-status.json")["status"], "completed")
                self.assertEqual(record["completed_updates"], 32)
                self.assertEqual([row["step"] for row in record["measurements"]], [0, 32])
                self.assertEqual(record["gradient_parameter_count"], 1340)
                self.assertTrue(result["complete_measurement_selection_prediction_refit_replay"])
                self.assertEqual(record["frozen_operations"], arm.startswith("frozen_"))
                self.assertEqual(record["fitting_work"]["updates"], 32)
                if arm.startswith("frozen_"):
                    self.assertEqual(record["refit_steps"], [])
                    self.assertEqual(record["fitting_work"]["linear_systems"], 0)
                    self.assertEqual(record["frozen_operation_checks"], 33)
                else:
                    self.assertEqual(record["refit_steps"], [0, 32])
                    self.assertEqual(record["fitting_work"]["affine_fit_examples"], 2 * 84)
                    self.assertEqual(record["fitting_work"]["linear_systems"], 8)

    def test_verifier_rejects_frozen_operation_retained_snapshot_missing_refit_and_prediction_tampering(self):
        frozen_dir, _, _, _ = self._fit("frozen-corruption", "frozen_warm")
        refit_dir, _, _, _ = self._fit("refit-corruption", "refit_warm")

        def rejected(original: Path, label: str):
            replay = self.root / (label + "-replay")
            replay.mkdir()
            write_json(replay / "protocol.json", self.protocol)
            with patch.object(worker.data, "generate", side_effect=lambda *args: self._fake_generated_rows()):
                with self.assertRaises(ContractError):
                    worker.verify_fit(engine, self.protocol, original, replay, worker.Work(self.protocol))

        map_path = frozen_dir / "parameters-0.json"
        original_map = read_json(map_path)
        changed_map = copy.deepcopy(original_map)
        changed_map["tensors"]["transition_bias"][0][0] += 0.05
        write_json(map_path, changed_map)
        rejected(frozen_dir, "bad-map")
        write_json(map_path, original_map)

        retained_path = frozen_dir / "retained-parameters.json"
        retained = read_json(retained_path)
        retained["tensors"]["coupling_first_bias"][0][0] += 0.05
        write_json(retained_path, retained)
        rejected(frozen_dir, "bad-retained")
        write_json(retained_path, self.snapshot)

        missing_refit = refit_dir / "refit-32.json"
        saved_refit = missing_refit.read_bytes()
        missing_refit.unlink()
        rejected(refit_dir, "missing-refit")
        missing_refit.write_bytes(saved_refit)

        predictions_path = refit_dir / "predictions.json"
        predictions = read_json(predictions_path)
        predictions["training"][0][0][0] += 0.125
        write_json(predictions_path, predictions)
        rejected(refit_dir, "bad-prediction")


if __name__ == "__main__":
    unittest.main()
