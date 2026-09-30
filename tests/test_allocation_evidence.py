from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from noetloom.allocation_worker import allocation_parity
from noetloom.contracts import ContractError, canonical_bytes
from noetloom.learning_data import episode
from noetloom.storage import RunWriter, StorageError, file_digest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("allocation_driver_tests", ROOT / "scripts/allocation.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class AllocationEvidenceTests(unittest.TestCase):
    def test_equal_payload_allocator_uses_cost_and_endpoint_quality(self):
        report = {"arms": {arm: {"family_payload_bytes": {"test_base": count},
                    "scored": {"families": {"test_base": {"accuracy": accuracy, "queries": 8}}}}
                  for arm, count, accuracy in [("top_one", 256, 0.5), ("dense", 1280, 1.0), ("adaptive", 512, 0.8)]}}
        control = driver.equal_payload_control(report)
        self.assertEqual(control["families"]["test_base"]["dense_probability"], 0.25)
        self.assertEqual(control["expected_accuracy"], 0.625)
        report["arms"]["adaptive"]["scored"]["families"]["test_base"]["accuracy"] = 0
        self.assertEqual(driver.equal_payload_control(report), control)
        report["arms"]["adaptive"]["family_payload_bytes"]["test_base"] = 1281
        with self.assertRaises(ContractError):
            driver.equal_payload_control(report)

    def test_gate_parity_refuses_decision_feature_score_and_read_corruption(self):
        row = episode(list(range(100)), 99, "base", "test_base-0000")
        predictions = [{"query_id": i, "prediction": 0, "logits": [0.0] * 5,
                        "continued": False, "gate_features": [0.2] * 6, "gate_score": -1.0}
                       for i in range(8)]
        receipt = {"results": [{"id": row["id"], "predictions": predictions,
                              "metrics": {"continued_queries": 0, "payload_reads": 8}}]}
        tensor = {"logits": [[0.0] * 5 for _ in range(8)], "predictions": [0] * 8,
                  "continued": [False] * 8, "gate_features": [[0.2] * 6 for _ in range(8)],
                  "gate_scores": [-1.0] * 8, "payload_reads": [1] * 8}
        self.assertEqual(allocation_parity(receipt, [row], tensor), 0.0)
        mutations = [lambda r: r["results"][0]["predictions"][0].__setitem__("continued", True),
                     lambda r: r["results"][0]["predictions"][0]["gate_features"].__setitem__(0, 0.4),
                     lambda r: r["results"][0]["predictions"][0].__setitem__("gate_score", float("nan")),
                     lambda r: r["results"][0]["metrics"].__setitem__("payload_reads", 9)]
        for mutate in mutations:
            altered = deepcopy(receipt)
            mutate(altered)
            with self.assertRaises(ContractError):
                allocation_parity(altered, [row], tensor)

    def test_export_cannot_change_parent_or_selected_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            parent = {"seed": 1103, "schema_version": "noetloom.cell_parameters.v1", "arm": "dense", "weights_fixture": [1.0]}
            gate = {"weights": [0.0] * 6, "bias": 1.0}
            values = {"parent.json": parent, "selected-gate.json": gate, "gate-step-32.json": gate,
                      "report.json": {"selected_step": 32, "validation_checkpoints": [{"step": 32, "objective": 0.2}, {"step": 64, "objective": 0.2}]},
                      "parameters-dense.json": parent,
                      "parameters-top_one.json": {**parent, "arm": "selective"},
                      "parameters-adaptive.json": {**parent, "schema_version": "noetloom.cell_parameters.v2", "arm": "adaptive", "gate": gate}}
            for name, value in values.items():
                (directory / name).write_bytes(canonical_bytes(value))
            driver.validate_parameters(directory, parent, 1103)
            altered = {**parent, "weights_fixture": [2.0]}
            (directory / "parameters-dense.json").write_bytes(canonical_bytes(altered))
            with self.assertRaisesRegex(ContractError, "frozen parent"):
                driver.validate_parameters(directory, parent, 1103)

    def test_manifest_binds_source_and_all_retained_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "payload.json").write_bytes(b"{}")
            manifest = {"schema_version": "noetloom.allocation_run.v1", "status": "passed",
                        "source": {"id": 1}, "artifacts": driver.learning_tools.artifacts(directory)}
            (directory / "manifest.json").write_bytes(canonical_bytes(manifest))
            with patch.object(driver, "identity", return_value={"id": 1}):
                driver.check_manifest(directory)
                (directory / "payload.json").write_bytes(b"{\"changed\":true}")
                with self.assertRaisesRegex(ContractError, "inventory"):
                    driver.check_manifest(directory)
                (directory / "payload.json").write_bytes(b"{}")
            with patch.object(driver, "identity", return_value={"id": 2}):
                with self.assertRaisesRegex(ContractError, "source differs"):
                    driver.check_manifest(directory)

    def test_failed_completion_admission_leaves_no_success_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            binary = directory / "binary"
            binary.write_bytes(b"fixture")
            writer = RunWriter(directory / "run", 1024 * 1024, 10)
            writer.write_json("report.json", {"status": "completed"})
            with patch.object(driver, "identity", return_value={}), \
                 patch.object(driver, "storage_snapshot", side_effect=StorageError("refused")):
                with self.assertRaisesRegex(StorageError, "refused"):
                    driver.finish(writer, {}, binary, file_digest(binary), {}, {})
            self.assertFalse((writer.directory / "manifest.json").exists())

    def test_uncertainty_uses_five_seed_pairs(self):
        self.assertEqual(driver.seed_interval([0.1] * 5)["low"], 0.1)
        with self.assertRaises(ContractError):
            driver.seed_interval([0.1] * 100)

    def test_new_preflight_cannot_hide_a_failed_seed_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            attempt = cache / "allocation-train-incomplete"
            attempt.mkdir()
            (attempt / "request.json").write_bytes(canonical_bytes({"seed": 1103, "admission": "old-preflight"}))
            (attempt / "protocol.json").write_bytes(canonical_bytes({"id": "EXP-0003"}))
            driver.refuse_existing_attempt(cache, {"id": "EXP-0003"}, 2207)
            with self.assertRaisesRegex(ContractError, "cannot reset"):
                driver.refuse_existing_attempt(cache, {"id": "EXP-0003"}, 1103)


if __name__ == "__main__":
    unittest.main()
