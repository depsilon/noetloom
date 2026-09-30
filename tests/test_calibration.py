from __future__ import annotations

import ast
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from helpers import ROOT
from noetloom.calibration_contracts import acquisition_gate, confirmation_decision, validate_calibration_protocol, validate_confirmation
from noetloom.calibration_data import decode, generate, orbit_key, partitions, render, score
from noetloom.calibration_model import parameter_count, scalar_forward, shapes, validate_snapshot
from noetloom.calibration_records import publish_fit, write
from noetloom.calibration_worker import require_confirmation_payloads, select_measurement, verify_selected
from noetloom.contracts import ContractError, canonical_bytes, load_policy, read_json
from noetloom.representation_data import generate as retired_data

sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("calibration_driver_tests", ROOT / "scripts/calibration.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
backup_spec = importlib.util.spec_from_file_location("backup_driver_tests", ROOT / "scripts/artifact_backup.py")
backup = importlib.util.module_from_spec(backup_spec)
backup_spec.loader.exec_module(backup)


def protocol():
    return read_json(ROOT / "experiments/EXP-0005/protocol.json")


def snapshot(arm):
    value = {"schema_version": "noetloom.calibration_parameters.v1", "role": "inference_parameters_only",
             "arm": arm, "seed": 1, "step": 0}
    for name, dimensions in shapes(arm).items():
        value[name] = [{"weights": [0.0] * (i * o), "bias": [0.0] * o} for i, o, _ in dimensions]
    return value


class CalibrationTests(unittest.TestCase):
    def test_registration_refuses_any_changed_experience_supervision_or_budget(self):
        p, policy = protocol(), load_policy(ROOT, "local-calibration")
        validate_calibration_protocol(p, policy)
        for key, replacement in (("network_during_run", True), ("external_pretrained_components", ["teacher"]),
                                  ("development_seeds", [1, 2, 3]), ("extra", 0)):
            altered = deepcopy(p)
            altered[key] = replacement
            with self.assertRaisesRegex(ContractError, "registered"):
                validate_calibration_protocol(altered, policy)
        with self.assertRaisesRegex(ContractError, "resource profile"):
            validate_calibration_protocol(p, load_policy(ROOT))

    def test_whole_relabeling_orbits_are_separated_and_development_does_not_render_final(self):
        p = protocol()
        split = partitions(p["data"])
        seen = set()
        for group in split.values():
            keys = {orbit_key(order, query) for order, query in group}
            self.assertEqual(len(keys), len(group))
            self.assertFalse(seen & keys)
            seen |= keys
        forbidden = set(split["confirmation"])
        def guarded(order, query, surface, transform="identity"):
            self.assertNotIn((order, query), forbidden)
            return render(order, query, surface, transform)
        with patch("noetloom.calibration_data.render", side_effect=guarded):
            data = generate(p, "mixed")
        self.assertEqual({k: len(v) for k, v in data.items()}, {"training": 1152, "validation": 288, "evaluation": 576})
        self.assertEqual(len({row["input_sha256"] for group in data.values() for row in group}), 2016)

    def test_scorer_known_order_and_query_reversal_for_every_surface_and_transform(self):
        order = (4, 1, 3, 0, 5, 2)
        for surface in ("ranks", "sequence", "relations"):
            for transform in ("identity", "row_permutation", "transpose"):
                self.assertEqual(decode(render(order, (1, 5), surface, transform)), 1)
                self.assertEqual(decode(render(order, (5, 1), surface, transform)), 0)
        field = render(order, (1, 5), "ranks")
        field[63] = 0
        with self.assertRaisesRegex(ContractError, "orientation"):
            decode(field)
        field = render(order, (1, 5), "relations")
        field[0] = 1.0
        with self.assertRaisesRegex(ContractError, "relation grammar"):
            decode(field)

    def test_actual_inputs_do_not_reuse_the_retired_experiment(self):
        old = retired_data(read_json(ROOT / "experiments/EXP-0004/protocol.json"))
        old_hashes = {row["input_sha256"] for key in ("training", "validation", "development", "test", "diagnostic") for row in old[key]}
        data = generate(protocol(), "mixed")
        new_hashes = {row["input_sha256"] for group in data.values() for row in group}
        self.assertFalse(old_hashes & new_hashes)

    def test_aggregate_accuracy_cannot_hide_a_failed_format_or_initialization(self):
        p = protocol()
        counts = {"identity/" + name: {"accuracy": 1.0} for name in p["data"]["surfaces"]}
        row = {"step": 512, "training": {"scored": counts}, "validation": {"scored": deepcopy(counts)}}
        self.assertTrue(acquisition_gate("mixed", row, p)["passed"])
        row["validation"]["scored"]["identity/sequence"]["accuracy"] = 0.84
        self.assertFalse(acquisition_gate("mixed", row, p)["passed"])
        del row["validation"]["scored"]["identity/sequence"]
        with self.assertRaisesRegex(ContractError, "omit"):
            acquisition_gate("mixed", row, p)
        row["validation"]["scored"] = deepcopy(counts)
        row["step"] = 0
        self.assertFalse(acquisition_gate("mixed", row, p)["passed"])

    def test_completed_fit_survives_real_post_fit_callback_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "protocol.json").write_bytes(canonical_bytes(protocol()))
            fit = {"completed_updates": 512, "measurements": [{"step": 512, "accuracy": 0.95}]}
            def fail():
                self.assertEqual(read_json(root / "fit.json"), fit)
                self.assertEqual(read_json(root / "fitting-status.json")["status"], "completed")
                raise ContractError("downstream native failure fixture")
            with self.assertRaisesRegex(ContractError, "downstream native"):
                publish_fit(root, fit, fail)
            self.assertEqual(read_json(root / "fit.json"), fit)
            self.assertEqual(read_json(root / "verification-status.json")["status"], "failed")
            self.assertFalse((root / "manifest.json").exists())

    def test_atomic_records_reject_escape_and_preserve_previous_record_on_budget_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "protocol.json").write_bytes(canonical_bytes(protocol()))
            write(root, "fit-progress.json", {"updates": 16})
            with self.assertRaises(ContractError):
                write(root, "../escape.json", {})
            p = protocol()
            p["budget"]["max_output_bytes_per_run"] = 1
            (root / "protocol.json").write_bytes(canonical_bytes(p))
            with self.assertRaisesRegex(ContractError, "reserved"):
                write(root, "fit-progress.json", {"updates": 32})
            self.assertEqual(read_json(root / "fit-progress.json"), {"updates": 16})

    def test_scalar_reference_and_snapshot_boundaries(self):
        for arm in protocol()["arms"]:
            value = snapshot(arm)
            self.assertEqual(sum(len(layer["weights"]) + len(layer["bias"]) for key in ("encoder", "solver") for layer in value[key]), parameter_count(arm))
            value["solver"][-1]["bias"] = [-0.75, 0.5]
            logits, intermediate = scalar_forward(value, [0.25] * 64)
            self.assertEqual(logits, [-0.75, 0.5])
            self.assertEqual(len(intermediate), 80 if arm == "bypass" else 16)
            altered = deepcopy(value)
            altered["encoder"][0]["weights"][0] = float("nan")
            with self.assertRaises(ContractError):
                validate_snapshot(altered)
            altered = deepcopy(value)
            altered["role"] = "exact_optimizer_resume"
            with self.assertRaises(ContractError):
                validate_snapshot(altered)

    def test_forward_modules_do_not_import_the_generator_or_scorer(self):
        for name in ("calibration_model.py", "calibration_torch.py"):
            tree = ast.parse((ROOT / "noetloom" / name).read_text())
            imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
            self.assertFalse(imports & {"calibration_data", "representation_data", "calibration_worker"})

    def test_failed_attempt_and_incomplete_stage_cannot_be_repeated_or_skipped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = {"experiment": "EXP-0005", "kind": "development", "arm": "shared_rows", "stage": "tiny",
                       "condition": "short", "seed": 7103, "original": None}
            old = root / "calibration-development-failed"
            old.mkdir()
            (old / "request.json").write_bytes(canonical_bytes(request))
            with self.assertRaisesRegex(ContractError, "already exists"):
                driver.admit(root, protocol(), request)
            request = {**request, "stage": "single"}
            with self.assertRaisesRegex(ContractError, "preceding stage"):
                driver.admit(root, protocol(), request)
            request = {**request, "stage": "tiny", "condition": "long"}
            with self.assertRaisesRegex(ContractError, "unsuccessful short"):
                driver.admit(root, protocol(), request)

    def test_one_passing_seed_cannot_admit_development_transformations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "request.json").write_bytes(canonical_bytes({"kind": "development", "stage": "mixed",
                "arm": "shared_rows", "condition": "short", "seed": 7103}))
            with patch.object(driver, "stage_selection", return_value=None), self.assertRaisesRegex(ContractError, "three-seed"):
                driver.require_transfer_selection(root, protocol(), root)
            with patch.object(driver, "stage_selection", return_value="long"), self.assertRaisesRegex(ContractError, "three-seed"):
                driver.require_transfer_selection(root, protocol(), root)
            with patch.object(driver, "stage_selection", return_value="short"):
                driver.require_transfer_selection(root, protocol(), root)

    def test_fitting_verification_never_renders_development_transforms_even_for_a_passing_seed(self):
        metrics = {"cross_entropy": 0.0, "scored": {"identity/" + s: {"accuracy": 1.0} for s in protocol()["data"]["surfaces"]}}
        selected = {"step": 512, "training": metrics, "validation": metrics}
        fit = {"measurements": [selected], "selected_measurement": 0, "acquisition": {"passed": True}}
        data = {"training": [{}], "validation": [{}], "evaluation": []}
        with patch("noetloom.calibration_worker.evaluate", return_value=metrics), \
                patch("noetloom.calibration_worker.write"), \
                patch("noetloom.calibration_worker.reference_check", return_value={"cases": 1}), \
                patch("noetloom.calibration_worker.diagnostics", return_value={}), \
                patch("noetloom.calibration_worker.generate") as generation:
            result = verify_selected(None, None, data, fit, protocol(), {"kind": "development", "stage": "mixed"}, Path("unused"))
            generation.assert_not_called()
            self.assertEqual(result["evaluation_cases"], 0)

    def test_confirmation_amendment_does_not_retroactively_change_pilot_selection(self):
        points = [{"step": 512, "validation": {"cross_entropy": 0.1}},
                  {"step": 2048, "validation": {"cross_entropy": 0.2}}]
        self.assertEqual(select_measurement(points, {"kind": "development", "stage": "mixed"}), 0)
        self.assertEqual(select_measurement(points, {"kind": "confirmation", "stage": "mixed", "checkpoint_selection": "last"}), 1)
        with self.assertRaisesRegex(ContractError, "confirmation amendment"):
            select_measurement(points, {"kind": "development", "stage": "mixed", "checkpoint_selection": "last"})
        registration = read_json(ROOT / "experiments/EXP-0005/confirmation.json")
        validate_confirmation(registration)
        registration["seeds"][0] += 1
        with self.assertRaisesRegex(ContractError, "frozen"):
            validate_confirmation(registration)

    def test_confirmation_distinguishes_acquisition_transfer_and_missing_seeds(self):
        registration = read_json(ROOT / "experiments/EXP-0005/confirmation.json")
        def scored(correct):
            return {"correct": correct, "total": 192, "class_support": [96, 96], "accuracy": correct / 192}
        results = {seed: {"acquisition": True, "run_status": "passed", "replay_status": "passed",
                         "outcomes": {key: {"status": "completed"} for key in ("fitting", "verification", "resource")},
                         "trained": {family + "/" + surface: scored(96 if family == "transpose" else 186)
                                     for family in ("identity", "row_permutation", "transpose") for surface in ("ranks", "sequence", "relations")},
                         "untrained": {family + "/" + surface: scored(96)
                                       for family in ("identity", "row_permutation", "transpose") for surface in ("ranks", "sequence", "relations")}}
                   for seed in registration["seeds"]}
        result = confirmation_decision(registration, results)
        self.assertEqual(result["decision"], "competent_baseline_confirmed")
        self.assertTrue(result["transfer"]["row_permutation"]["retained"])
        self.assertFalse(result["transfer"]["transpose"]["retained"])
        for key in ("run_status", "replay_status"):
            altered = deepcopy(results)
            altered[registration["seeds"][0]][key] = "failed"
            self.assertEqual(confirmation_decision(registration, altered)["decision"], "not_confirmed")
        for key in ("fitting", "verification", "resource"):
            altered = deepcopy(results)
            altered[registration["seeds"][0]]["outcomes"][key]["status"] = "failed"
            self.assertEqual(confirmation_decision(registration, altered)["decision"], "not_confirmed")
        results[registration["seeds"][0]]["acquisition"] = False
        self.assertEqual(confirmation_decision(registration, results)["decision"], "not_confirmed")
        del results[registration["seeds"][0]]
        self.assertEqual(confirmation_decision(registration, results)["decision"], "not_confirmed")

    def test_historical_summary_checks_archived_source_without_admitting_current_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = {"files": [{"path": "old.py", "sha256": "a" * 64}]}
            stored = {"schema_version": "noetloom.calibration_run.v1", "status": "passed", "artifacts": [],
                      "source": old, "source_commit": "b" * 40}
            (root / "manifest.json").write_bytes(canonical_bytes(stored))
            with patch.object(driver.supervisor, "artifacts", return_value=[]), \
                    patch.object(driver, "source_at_revision", return_value=old), \
                    patch.object(driver, "identity", return_value={"files": []}):
                self.assertEqual(driver.manifest(root, current_source=False), stored)
                with self.assertRaisesRegex(ContractError, "source differs"):
                    driver.manifest(root)
            with patch.object(driver.supervisor, "artifacts", return_value=[]), \
                    patch.object(driver, "source_at_revision", return_value={"files": []}):
                with self.assertRaisesRegex(ContractError, "source differs"):
                    driver.manifest(root, current_source=False)

    def test_confirmation_replay_requires_both_final_and_initialization_control_payloads(self):
        counts = {"identity/" + surface: {"accuracy": 1.0} for surface in protocol()["data"]["surfaces"]}
        selected = {"step": 2048, "training": {"scored": counts}, "validation": {"scored": counts}}
        request = {"kind": "confirmation", "stage": "mixed"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ContractError, "payloads"):
                require_confirmation_payloads(root, request, selected, protocol())
            (root / "evaluation-data.json").write_text("{}")
            with self.assertRaisesRegex(ContractError, "payloads"):
                require_confirmation_payloads(root, request, selected, protocol())
            (root / "untrained.json").write_text("{}")
            require_confirmation_payloads(root, request, selected, protocol())
            selected["step"] = 0
            with self.assertRaisesRegex(ContractError, "payloads"):
                require_confirmation_payloads(root, request, selected, protocol())


if __name__ == "__main__":
    unittest.main()
