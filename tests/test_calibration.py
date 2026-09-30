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
from noetloom.calibration_contracts import acquisition_gate, validate_calibration_protocol
from noetloom.calibration_data import decode, generate, orbit_key, partitions, render, score
from noetloom.calibration_model import parameter_count, scalar_forward, shapes, validate_snapshot
from noetloom.calibration_records import publish_fit, write
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


if __name__ == "__main__":
    unittest.main()
