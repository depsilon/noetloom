"""Synthetic coverage for EXP-0009 affine worker accounting and replay."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from noetloom.contracts import ContractError, canonical_bytes, read_json
from noetloom import affine_coordinates_worker as worker

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "experiments/EXP-0009/protocol.json"

try:
    from noetloom import coordinates_torch as engine
except ImportError:
    engine = None


def protocol_fixture():
    protocol = read_json(PROTOCOL_PATH)
    protocol["training"]["steps"]["one"] = 16
    protocol["training"]["measurement_steps"]["one"] = [0, 8, 16]
    protocol["solver"].update(interval=8, training_pairs=84, per_action_pairs=21)
    return protocol


def write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_bytes(value))


class AffineWorkerContractTests(unittest.TestCase):
    def test_work_enforces_affine_example_and_linear_system_ceilings(self):
        protocol = protocol_fixture()
        protocol["budget"]["max_affine_fit_examples_per_run"] = 3
        protocol["budget"]["max_linear_systems_per_run"] = 2
        work = worker.Work(protocol)
        work.add("affine_fit_examples", 3)
        work.add("linear_systems", 2)
        with self.assertRaises(ContractError):
            work.add("affine_fit_examples", 1)
        with self.assertRaises(ContractError):
            work.add("linear_systems", 1)

    def test_refit_schedule_includes_zero_intervals_and_final_step(self):
        protocol = protocol_fixture()
        self.assertEqual(worker.refit_steps(protocol, "one"), [0, 8, 16])
        protocol["training"]["steps"]["one"] = 17
        self.assertEqual(worker.refit_steps(protocol, "one"), [0, 8, 16, 17])

    def test_solver_rows_checks_counts_without_requesting_heldout_splits(self):
        protocol = protocol_fixture()
        rows = worker.synthetic()
        dataset = {"training": rows, "validation": []}
        with patch.object(worker.data, "generate", return_value=dataset) as generate:
            self.assertEqual(worker.solver_rows(protocol), rows)
            generate.assert_called_once_with(protocol, "nonlinear", "one")
        with patch.object(worker.data, "generate", return_value={"training": rows[:-1]}) as generate:
            with self.assertRaises(ContractError):
                worker.solver_rows(protocol)
            generate.assert_called_once_with(protocol, "nonlinear", "one")


@unittest.skipIf(engine is None, "optional PyTorch backend is unavailable")
class AffineWorkerTorchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine.torch.set_num_threads(1)

    def setUp(self):
        self.protocol = protocol_fixture()
        self.rows = worker.synthetic()
        self.dataset = {"training": self.rows, "validation": copy.deepcopy(self.rows)}

    def _make_fit(self, arm: str):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        original = root / "original"
        replay = root / "replay"
        original.mkdir()
        replay.mkdir()
        request = {"kind": "fit", "stage": "one", "arm": arm, "seed": 29,
                   "condition": "lr003"}
        write_json(original / "protocol.json", self.protocol)
        write_json(replay / "protocol.json", self.protocol)
        write_json(original / "request.json", request)
        generate = patch.object(worker.data, "generate", return_value=self.dataset)
        generate.start()
        self.addCleanup(generate.stop)
        worker.fit(engine, self.protocol, request, original, worker.Work(self.protocol))
        return temp, original, replay, request

    def test_joint_and_refit_fit_replay_complete_curves_with_charged_solves(self):
        for arm in ("joint", "refit"):
            with self.subTest(arm=arm):
                temp, original, replay, request = self._make_fit(arm)
                self.addCleanup(temp.cleanup)
                record = read_json(original / "fit.json")
                self.assertEqual(read_json(original / "fitting-status.json")["status"], "completed")
                self.assertEqual(record["completed_updates"], 16)
                self.assertEqual([row["step"] for row in record["measurements"]], [0, 8, 16])
                work = worker.Work(self.protocol)
                replay_result = worker.verify_fit(engine, self.protocol, original, replay, work)
                self.assertTrue(replay_result["complete_measurement_selection_prediction_refit_replay"])
                if arm == "joint":
                    self.assertEqual(record["refit_steps"], [])
                    self.assertEqual(record["fitting_work"]["linear_systems"], 0)
                    self.assertEqual(record["fitting_work"]["affine_fit_examples"], 0)
                    self.assertEqual(work.counts["linear_systems"], 0)
                else:
                    self.assertEqual(record["refit_steps"], [0, 8, 16])
                    self.assertEqual(record["fitting_work"]["affine_fit_examples"], 3 * 84)
                    self.assertEqual(record["fitting_work"]["linear_systems"], 12)
                    self.assertEqual(work.counts["affine_fit_examples"], 3 * 84)
                    self.assertEqual(work.counts["linear_systems"], 12)

    def test_refit_arm_freezes_transitions_during_gradient_updates_and_solves(self):
        protocol = copy.deepcopy(self.protocol)
        model = engine.Model("reversible", 43)
        optimizer = worker.optimizer_for(engine, model, "refit", 0.003)
        before_weight, before_bias = model.transition_weight.detach().clone(), model.transition_bias.detach().clone()
        before_coupling = model.coupling_last_bias.detach().clone()
        work = worker.Work(protocol)
        from noetloom import state_rep_worker as common
        common.update(engine, model, optimizer, self.rows[:8], protocol, work)
        self.assertTrue(engine.torch.equal(before_weight, model.transition_weight))
        self.assertTrue(engine.torch.equal(before_bias, model.transition_bias))
        self.assertFalse(engine.torch.equal(before_coupling, model.coupling_last_bias))
        coupling_after_update = {name: value.detach().clone() for name, value in model.named_parameters()
                                 if name.startswith("coupling_")}
        worker.refit(engine, model, self.rows, protocol, work)
        for name, parameter in model.named_parameters():
            if name in coupling_after_update:
                self.assertTrue(engine.torch.equal(coupling_after_update[name], parameter))

    def test_failed_action_solve_keeps_every_transition_and_coupling_parameter_atomic(self):
        protocol = copy.deepcopy(self.protocol)
        rows = copy.deepcopy(self.rows)
        for row in rows:
            if row["actions"] == [3]:
                row["initial"] = [0.0] * 10
        model = engine.Model("reversible", 47)
        before = {name: value.detach().clone() for name, value in model.named_parameters()}
        with self.assertRaises(ContractError):
            worker.refit(engine, model, rows, protocol, worker.Work(protocol))
        for name, parameter in model.named_parameters():
            self.assertTrue(engine.torch.equal(before[name], parameter), name)

    def test_refit_replay_rejects_tampered_snapshot_coverage_and_predictions(self):
        temp, original, _, request = self._make_fit("refit")
        self.addCleanup(temp.cleanup)

        def replay_fails(label):
            replay = Path(temp.name) / label
            replay.mkdir()
            write_json(replay / "protocol.json", self.protocol)
            with self.assertRaises(ContractError):
                worker.verify_fit(engine, self.protocol, original, replay, worker.Work(self.protocol))

        snapshot_path = original / "refit-8.json"
        valid_snapshot = read_json(snapshot_path)
        snapshot = copy.deepcopy(valid_snapshot)
        snapshot["tensors"]["transition_weight"][0][0][0] += 0.125
        write_json(snapshot_path, snapshot)
        replay_fails("bad-snapshot")
        write_json(snapshot_path, valid_snapshot)

        refits_path = original / "refits.json"
        refits = read_json(refits_path)
        write_json(refits_path, {"refits": refits["refits"][:-1]})
        replay_fails("bad-coverage")
        write_json(refits_path, refits)

        predictions_path = original / "predictions.json"
        predictions = read_json(predictions_path)
        predictions["training"][0][0][0] += 0.01
        write_json(predictions_path, predictions)
        replay_fails("bad-prediction")

    def test_evaluation_reports_identity_composition_and_both_suffix_metrics(self):
        protocol = copy.deepcopy(self.protocol)
        model = engine.Model("reversible", 53)
        torch = engine.torch
        with torch.no_grad():
            model.coupling_first_weight.zero_()
            model.coupling_first_bias.zero_()
            model.coupling_last_weight.zero_()
            model.coupling_last_bias.zero_()
            model.transition_weight.copy_(torch.eye(10).expand(4, -1, -1))
            model.transition_bias.zero_()
        first, second = [0.7] * 10, [-0.8] * 10
        rows = [
            {"initial": first, "actions": [0, 1], "targets": [first, first], "family": "short"},
            {"initial": second, "actions": [2, 3, 1], "targets": [second, second, second], "family": "long"},
        ]
        pairs = []
        for actions_a, actions_b, family in (([0], [1], "pair_a"), ([2, 3], [3, 2], "pair_b")):
            current = [0.65 if family == "pair_a" else -0.75] * 10
            history_a = {"initial": current, "actions": actions_a, "targets": [current] * len(actions_a), "family": family}
            history_b = {"initial": current, "actions": actions_b, "targets": [current] * len(actions_b), "family": family}
            pairs.append({"history_a": history_a, "history_b": history_b, "current": current,
                          "suffix": [0, 2], "targets": [current, current], "family": family})
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            write_json(directory / "protocol.json", protocol)
            work = worker.Work(protocol)
            with (patch.object(worker.data, "development", return_value=rows),
                  patch.object(worker.data, "continuations", return_value=pairs),
                  patch.object(worker.data, "audit", return_value={"reverse_order_sensitivity": {}})):
                result = worker.evaluate_model(engine, protocol, model, directory, work)
        self.assertTrue(result["competence"]["passed"])
        self.assertEqual(result["development"]["scored"]["all"]["all_prefix_exact_accuracy"], 1.0)
        self.assertEqual(result["development"]["scored"]["family/short"]["cases"], 1)
        self.assertEqual(result["development"]["scored"]["family/long"]["cases"], 1)
        self.assertEqual(result["continuation"]["scored"]["all"]["both_suffix_accuracy"], 1.0)
        self.assertEqual(result["continuation"]["scored"]["family/pair_a"]["both_suffix_accuracy"], 1.0)
        self.assertEqual(result["continuation"]["scored"]["family/pair_b"]["both_suffix_accuracy"], 1.0)
        self.assertEqual(result["controls"]["zero_initial_state"]["all"]["all_prefix_exact_accuracy"], 0.0)
        self.assertEqual(result["controls"]["zero_state_after_history"]["scored"]["all"]["both_suffix_accuracy"], 0.0)


if __name__ == "__main__":
    unittest.main()
