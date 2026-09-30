from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from helpers import ROOT
from noetloom.contracts import ContractError, canonical_bytes, read_json
from noetloom import representation_common as common
from noetloom.representation_worker import parity
from noetloom.storage import RunWriter, StorageError, file_digest

sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("representation_driver_tests", ROOT / "scripts/representation.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def protocol() -> dict:
    return read_json(ROOT / "experiments/EXP-0004/protocol.json")


def parameter_artifact(arm: str, seed: int = 6101, step: int = 0) -> dict:
    construction, solver = common.shapes(arm)

    def layer(inputs: int, outputs: int, activation: str) -> dict:
        return {"input_dim": inputs, "output_dim": outputs, "weights": [0.0] * (inputs * outputs),
                "bias": [0.0] * outputs, "activation": activation}

    return {"schema_version": "noetloom.representation_parameters.v1", "arm": arm, "seed": seed,
            "step": step,
            "construction": [layer(i, o, "tanh" if index == 0 else "identity")
                             for index, (i, o) in enumerate(construction)],
            "static_scores": [0.0] * 1024 if arm == "static" else [],
            "solver": [layer(i, o, "tanh" if index < 2 else "identity")
                       for index, (i, o) in enumerate(solver)]}


def write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_bytes(value))


class RepresentationEvidenceTests(unittest.TestCase):
    def test_decision_requires_every_control_intervention_and_acquisition_gate(self):
        registered = protocol()
        reports = {}
        for arm in registered["arms"]:
            for seed in registered["seeds"]:
                accuracy = 0.95 if arm == "conditional" else 0.70
                reports[(arm, seed)] = {
                    "seed": seed, "steps": 1024, "selected_step": 512,
                    "training_proxy_ops": common.training_proxy(arm, 1024),
                    "case_presentations": 8560 if arm == "conditional" else 7792,
                    "results": {"scored": {family: {"accuracy": accuracy}
                                             for family in driver.FAMILIES}},
                    "shifted": {"scored": {family: {"accuracy": 0.60}
                                            for family in driver.FAMILIES}},
                    "diagnostic": {"all_three_agreement": 0.90},
                    "fitting_validation_seconds": 1.0, "peak_rss_bytes": 1024,
                    "restart_passed": True, "restart_cases": 8,
                }
        result = driver.aggregate(registered, reports)
        self.assertEqual(result["decision"], "retain")
        self.assertTrue(all(result["gates"].values()))

        # Winning against two controls cannot rescue a failure against the third.
        for control in ("fixed_small", "fixed_large", "static"):
            altered = deepcopy(reports)
            for seed in registered["seeds"]:
                altered[(control, seed)]["results"]["scored"] = deepcopy(
                    altered[("conditional", seed)]["results"]["scored"])
            result = driver.aggregate(registered, altered)
            self.assertEqual(result["decision"], "reject_registered_configuration")
            self.assertFalse(result["gates"]["beats_all_controls"])
        altered = deepcopy(reports)
        for seed in registered["seeds"]:
            altered[("conditional", seed)]["shifted"] = deepcopy(
                altered[("conditional", seed)]["results"])
        self.assertFalse(driver.aggregate(registered, altered)["gates"]["conditional_transport_matters"])

        altered = deepcopy(reports)
        for report in altered.values():
            report["results"]["scored"]["base"]["accuracy"] = 0.69
        result = driver.aggregate(registered, altered)
        self.assertEqual(result["decision"], "reject_registered_configuration")
        self.assertEqual(result["comparison_status"], "inconclusive_task_acquisition_failed")
        altered.pop(("conditional", registered["seeds"][-1]))
        with self.assertRaisesRegex(ContractError, "incomplete"):
            driver.aggregate(registered, altered)

    def test_arm_shapes_parameter_counts_forward_work_and_parameter_validation(self):
        expected = {
            "fixed_small": ([], [(64, 32), (32, 32), (32, 2)], 3202, 6402),
            "fixed_large": ([], [(64, 160), (160, 160), (160, 2)], 36482, 72962),
            "conditional": ([(64, 16), (16, 1024)], [(16, 32), (32, 32), (32, 2)], 20114, 46354),
            "static": ([], [(16, 32), (32, 32), (32, 2)], 2690, 10482),
        }
        for arm, (construction, solver, count, operations) in expected.items():
            with self.subTest(arm=arm):
                self.assertEqual(common.shapes(arm), (construction, solver))
                self.assertEqual(common.parameter_count(arm), count)
                self.assertEqual(common.forward_ops(arm), operations)
                common.validate_parameters(parameter_artifact(arm))
        with self.assertRaises(ContractError):
            common.shapes("invented")
        with self.assertRaises(ContractError):
            common.parameter_count("invented")

    def test_hand_zero_artifacts_reject_unknown_nonfinite_bool_and_architecture_corruption(self):
        common.validate_parameters(parameter_artifact("fixed_small"))
        mutations = [
            lambda value: value.__setitem__("unexpected", 1),
            lambda value: value["solver"][0]["weights"].__setitem__(0, float("inf")),
            lambda value: value["solver"][0]["weights"].__setitem__(0, True),
            lambda value: value["solver"][0].__setitem__("input_dim", 63),
            lambda value: value["solver"][0].__setitem__("activation", "identity"),
            lambda value: value.__setitem__("static_scores", [0.0] * 1023),
        ]
        for mutate in mutations:
            value = parameter_artifact("static" if mutate is mutations[-1] else "fixed_small")
            with self.subTest(mutate=mutate), self.assertRaises(ContractError):
                mutate(value)
                common.validate_parameters(value)

    def test_native_tensor_parity_rejects_row_and_statistics_corruption(self):
        tensor = {"predictions": [0], "logits": [[0.25, -0.5]],
                  "intermediates": [[0.1] * 16], "transport_entropy": 1.5,
                  "transport_variance": 0.02}
        receipt = {"schema_version": "noetloom.native_representation.v1",
                   "rows": [{"prediction": 0, "logits": [0.25, -0.5], "intermediate": [0.1] * 16}],
                   "transport_entropy": 1.5, "transport_variance": 0.02}
        self.assertEqual(parity(receipt, tensor), 0.0)
        mutations = [
            lambda value: value["rows"][0].__setitem__("prediction", 1),
            lambda value: value["rows"][0].__setitem__("prediction", True),
            lambda value: value["rows"][0]["logits"].__setitem__(0, 0.25021),
            lambda value: value["rows"][0]["intermediate"].__setitem__(0, 0.10021),
            lambda value: value["rows"].pop(),
            lambda value: value["rows"][0]["logits"].__setitem__(0, float("nan")),
            lambda value: value.__setitem__("transport_entropy", 1.6),
        ]
        for mutate in mutations:
            altered = deepcopy(receipt)
            with self.subTest(mutate=mutate), self.assertRaises(ContractError):
                mutate(altered)
                parity(altered, tensor)

    def test_seed_interval_is_five_finite_pairs(self):
        interval = driver.seed_interval([0.1] * 5)
        self.assertEqual(interval["low"], 0.1)
        self.assertEqual(interval["mean"], 0.1)
        self.assertEqual(interval["high"], 0.1)
        for values in ([0.1] * 4, [0.1] * 6, [0.1, 0.1, float("nan"), 0.1, 0.1]):
            with self.subTest(values=values), self.assertRaises(ContractError):
                driver.seed_interval(values)

    def test_failed_attempt_blocks_same_arm_seed_even_with_changed_admission(self):
        registered = protocol()
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            attempt = cache / "representation-train-failed"
            attempt.mkdir()
            write_json(attempt / "protocol.json", registered)
            write_json(attempt / "request.json", {"arm": "conditional", "seed": 6101,
                                                   "admission": "/different/preflight"})
            with self.assertRaises(ContractError):
                driver.refuse_existing_attempt(cache, registered, "conditional", 6101)

            changed_limit = deepcopy(registered)
            changed_limit["budget"]["max_training_attempts"] = 1
            with self.assertRaises(ContractError):
                driver.refuse_existing_attempt(cache, changed_limit, "fixed_small", 6203)

    def test_finish_does_not_write_passed_manifest_when_final_storage_admission_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "binary"
            binary.write_bytes(b"fixture executable")
            writer = RunWriter(root / "run", 1024 * 1024, 10)
            writer.write_json("report.json", {"status": "completed"})
            source = {"fixture": "source"}
            completed = subprocess.CompletedProcess([], 0, stdout="fixture-head\n", stderr="")
            with patch.object(driver, "identity", return_value=source), \
                    patch.object(driver.subprocess, "run", return_value=completed), \
                    patch.object(driver, "storage_snapshot", side_effect=StorageError("refused")):
                with self.assertRaisesRegex(StorageError, "refused"):
                    driver.finish(writer, source, binary, file_digest(binary), {}, {})
            self.assertFalse((writer.directory / "manifest.json").exists())

    def test_manifest_binds_nested_artifacts_hashes_and_source_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "nested").mkdir()
            (directory / "nested/data.json").write_bytes(b"{}")
            source = {"fixture": 1}
            manifest = {"schema_version": "noetloom.representation_run.v1", "status": "passed",
                        "source": source, "artifacts": driver.learning_tools.artifacts(directory)}
            write_json(directory / "manifest.json", manifest)
            with patch.object(driver, "identity", return_value=source):
                driver.check_manifest(directory)
                (directory / "nested/data.json").write_bytes(b'{"modified":true}')
                with self.assertRaisesRegex(ContractError, "artifact inventory"):
                    driver.check_manifest(directory)
                (directory / "nested/data.json").write_bytes(b"{}")
                (directory / "extra.json").write_bytes(b"{}")
                with self.assertRaisesRegex(ContractError, "artifact inventory"):
                    driver.check_manifest(directory)
                (directory / "extra.json").unlink()
            with patch.object(driver, "identity", return_value={"fixture": 2}):
                with self.assertRaisesRegex(ContractError, "source differs"):
                    driver.check_manifest(directory)

    def test_selection_checks_admitted_checkpoints_identity_work_and_presentations(self):
        registered = protocol()
        arm, seed, steps = "fixed_small", 6101, 1024
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            checkpoints = []
            for step, loss in ((256, 0.4), (512, 0.1), (1024, 0.2)):
                artifact = parameter_artifact(arm, seed, step)
                write_json(directory / f"checkpoint-{step}.json", artifact)
                checkpoints.append({"step": step, "cross_entropy": loss})
            selected = parameter_artifact(arm, seed, 512)
            write_json(directory / "selected.json", selected)
            report = {"arm": arm, "seed": seed, "steps": steps,
                      "validation_checkpoints": checkpoints, "selected_step": 512,
                      "parameter_count": common.parameter_count(arm),
                      "training_proxy_ops": common.training_proxy(arm, steps),
                      "forward_scalar_ops": common.forward_ops(arm),
                      "case_presentations": steps * 6 + 288 + 768 + 576 + 16}
            write_json(directory / "report.json", report)
            manifest = {"kind": "train", "arm": arm, "seed": seed}
            self.assertEqual(driver.validate_selection(directory, registered, manifest, steps), selected)

            invalids = []
            wrong_report_seed = deepcopy(report)
            wrong_report_seed["seed"] = seed + 1
            invalids.append((wrong_report_seed, manifest, selected))
            wrong_manifest_seed = deepcopy(manifest)
            wrong_manifest_seed["seed"] = seed + 1
            invalids.append((report, wrong_manifest_seed, selected))
            wrong_selected_step = deepcopy(report)
            wrong_selected_step["selected_step"] = 256
            invalids.append((wrong_selected_step, manifest, selected))
            for field, value in (("parameter_count", 1), ("training_proxy_ops", 1),
                                 ("forward_scalar_ops", 1), ("case_presentations", 1)):
                wrong_work = deepcopy(report)
                wrong_work[field] = value
                invalids.append((wrong_work, manifest, selected))
            wrong_checkpoint = parameter_artifact(arm, seed, 512)
            wrong_checkpoint["solver"][0]["weights"][0] = 0.5
            write_json(directory / "checkpoint-512.json", wrong_checkpoint)
            with self.assertRaises(ContractError):
                driver.validate_selection(directory, registered, manifest, steps)
            write_json(directory / "checkpoint-512.json", selected)
            wrong_selected = deepcopy(selected)
            wrong_selected["seed"] = seed + 1
            invalids.append((report, manifest, wrong_selected))

            for bad_report, bad_manifest, bad_selected in invalids:
                with self.subTest(report=bad_report, manifest=bad_manifest):
                    write_json(directory / "report.json", bad_report)
                    write_json(directory / "selected.json", bad_selected)
                    with self.assertRaises(ContractError):
                        driver.validate_selection(directory, registered, bad_manifest, steps)


if __name__ == "__main__":
    unittest.main()
