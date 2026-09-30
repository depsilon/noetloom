from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from noetloom.contracts import ContractError, canonical_bytes
from noetloom.learning_data import episode
from noetloom.learning_worker import parity, score
from noetloom.storage import RunWriter, StorageError, file_digest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("learning_driver_tests", ROOT / "scripts/learning.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class LearningEvidenceTests(unittest.TestCase):
    def test_supervisor_uses_live_samples_then_requires_strict_completion(self):
        for final_failure in (False, True):
            with self.subTest(final_failure=final_failure), tempfile.TemporaryDirectory() as temporary:
                child = SimpleNamespace(pid=333, returncode=0, poll=Mock(side_effect=[None, 0, 0]))
                sampled = []

                def inventory(path, *, live=False):
                    sampled.append(live)
                    if not live and final_failure:
                        raise FileNotFoundError("retained entry disappeared after exit")
                    return 0

                with patch.object(driver.subprocess, "Popen", return_value=child), \
                        patch.object(driver.subprocess, "run", return_value=SimpleNamespace(stdout="333 333 1\n")), \
                        patch.object(driver.time, "sleep"), \
                        patch.object(driver, "tree_bytes", side_effect=inventory), \
                        patch.object(driver, "storage_snapshot", return_value={}) as snapshot:
                    if final_failure:
                        with self.assertRaisesRegex(FileNotFoundError, "after exit"):
                            driver.supervised(["fixture"], {}, Path(temporary), {}, 10, 4096, 4096)
                    else:
                        result = driver.supervised(["fixture"], {}, Path(temporary), {}, 10, 4096, 4096)
                        self.assertEqual(result["sampled_process_group_peak_rss_bytes"], 1024)
                        self.assertEqual([call.kwargs for call in snapshot.call_args_list], [{"live": True}, {}])
                self.assertEqual(sampled, [True, False])

    def setUp(self):
        self.row = episode(list(range(100)), 99, "base", "test_base-0000")
        self.predictions = [{"query_id": answer["query_id"], "prediction": answer["expected"],
                             "logits": [1.0 if value == answer["expected"] else 0.0 for value in range(5)]}
                            for answer in self.row["answers"]]
        self.receipt = {"results": [{"id": self.row["id"], "predictions": self.predictions,
                                    "metrics": {"payload_reads": 8, "elapsed_ns": 100}}]}
        self.tensor = {"logits": [p["logits"] for p in self.predictions],
                       "predictions": [p["prediction"] for p in self.predictions]}

    def test_scoring_known_answers_and_corrupted_labels(self):
        self.assertEqual(score(self.receipt, [self.row])["accuracy"], 1.0)
        altered = deepcopy(self.row)
        altered["answers"][0]["expected"] = (altered["answers"][0]["expected"] + 1) % 4
        with self.assertRaisesRegex(ContractError, "independent exact reference"):
            score(self.receipt, [altered])
        altered = deepcopy(self.receipt)
        altered["results"][0]["predictions"][0]["query_id"] = 1
        with self.assertRaises(ContractError):
            score(altered, [self.row])

    def test_independent_parity_refuses_logits_classes_and_query_omission(self):
        self.assertEqual(parity(self.receipt, [self.row], self.tensor), 0.0)
        for mutation in (
            lambda r: r["results"][0]["predictions"][0]["logits"].__setitem__(0, 0.5),
            lambda r: r["results"][0]["predictions"][0].__setitem__("prediction", 99),
            lambda r: r["results"][0]["predictions"].pop(),
        ):
            changed = deepcopy(self.receipt)
            mutation(changed)
            with self.assertRaises(ContractError):
                parity(changed, [self.row], self.tensor)

    def test_inventory_does_not_ignore_nested_manifest_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "payload.json").write_bytes(b"{}")
            manifest = {"schema_version": "noetloom.learning_run.v1", "status": "passed",
                        "source": {}, "artifacts": driver.artifacts(directory)}
            (directory / "manifest.json").write_bytes(canonical_bytes(manifest))
            driver.check_manifest(directory, current=False)
            (directory / "state").mkdir()
            (directory / "state/manifest.json").write_bytes(b"{}")
            with self.assertRaisesRegex(ContractError, "inventory"):
                driver.check_manifest(directory, current=False)

    def test_completion_cannot_precede_final_storage_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            binary = directory / "binary"
            binary.write_bytes(b"fixture")
            writer = RunWriter(directory / "run", 1024 * 1024, 10)
            writer.write_json("report.json", {"status": "completed"})
            with patch.object(driver, "identity", return_value={}), \
                 patch.object(driver, "storage_snapshot", side_effect=StorageError("refused")):
                with self.assertRaisesRegex(StorageError, "refused"):
                    driver._finish(writer, {}, binary, file_digest(binary), {}, {})
            self.assertFalse((writer.directory / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
