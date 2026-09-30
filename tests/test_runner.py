from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, policy, small_protocol, write_json
from noetloom.cli import doctor
from noetloom.contracts import ContractError, read_json
from noetloom.runner import run_experiment, verify_run
from noetloom.storage import StorageError, file_digest


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="noetloom-run-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "repo"
        (self.root / "config").mkdir(parents=True)
        shutil.copytree(ROOT / "noetloom", self.root / "noetloom", ignore=shutil.ignore_patterns("__pycache__"))
        self.policy = policy()
        self.policy.update(min_free_disk_bytes=1, max_workspace_bytes=16 * 1024 * 1024,
                           max_run_output_bytes=1024 * 1024)
        write_json(self.root / "config/resource-policy.json", self.policy)
        shutil.copyfile(ROOT / "config/resource-policy-ci.json", self.root / "config/resource-policy-ci.json")
        self.protocol_path = self.root / "protocol.json"
        self.protocol = small_protocol()
        write_json(self.protocol_path, self.protocol)
        self.cache = self.base / "cache"

    def run_protocol(self) -> Path:
        result = self.invoke("run", self.protocol_path, "--cache", self.cache)
        return Path(result["directory"])

    def cli(self, *args) -> tuple[int, dict]:
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        result = subprocess.run([sys.executable, "-B", "-m", "noetloom", *map(str, args)],
                                cwd=self.root, capture_output=True, text=True, timeout=10,
                                env=environment)
        self.assertIn(result.returncode, (0, 1, 2), result.stderr)
        return result.returncode, json.loads(result.stderr if result.returncode == 2 else result.stdout)

    def invoke(self, *args) -> dict:
        code, payload = self.cli(*args)
        if code == 2:
            error = StorageError if payload["code"] == "storage_refused" else ContractError
            raise error(payload["message"])
        return payload

    def verify(self, directory: Path) -> dict:
        return self.invoke("verify-run", directory)

    def refresh_manifest(self, directory: Path, name: str) -> None:
        manifest_path = directory / "manifest.json"
        manifest = read_json(manifest_path)
        for entry in manifest["artifacts"]:
            if entry["path"] == name:
                entry["bytes"] = (directory / name).stat().st_size
                entry["sha256"] = file_digest(directory / name)
        write_json(manifest_path, manifest)

    def test_complete_run_has_replayable_prediction_evidence(self):
        directory = self.run_protocol()
        result = self.verify(directory)
        self.assertEqual(result["harness_verdict"], "passed")
        self.assertEqual(result["predictions_replayed"], 264)
        self.assertEqual(result["manifest_sha256"], file_digest(directory / "manifest.json"))
        self.assertFalse((self.cache / ".noetloom-run.lock").exists())

    def test_rejects_corruption_before_and_after_manifest_rehash(self):
        directory = self.run_protocol()
        predictions = directory / "predictions.jsonl"
        lines = predictions.read_text().splitlines()
        row = json.loads(lines[0])
        row["predicted"] = 999
        lines[0] = json.dumps(row)
        predictions.write_text("\n".join(lines) + "\n")
        with self.assertRaisesRegex(ContractError, "identity mismatch"):
            self.verify(directory)
        self.refresh_manifest(directory, "predictions.jsonl")
        with self.assertRaisesRegex(ContractError, "prediction stream"):
            self.verify(directory)

    def test_fabricated_scores_are_not_rescued_by_valid_hashes(self):
        directory = self.run_protocol()
        report = read_json(directory / "report.json")
        report["evaluation"]["totals"]["no_memory"]["correct"] += 1
        write_json(directory / "report.json", report)
        self.refresh_manifest(directory, "report.json")
        with self.assertRaisesRegex(ContractError, "scores or verdict"):
            self.verify(directory)

    def test_boolean_claim_cannot_be_replaced_by_equal_numeric_value(self):
        directory = self.run_protocol()
        report = read_json(directory / "report.json")
        report["evaluation"]["learning_demonstrated"] = 0
        write_json(directory / "report.json", report)
        self.refresh_manifest(directory, "report.json")
        with self.assertRaisesRegex(ContractError, "scores or verdict"):
            self.verify(directory)

    def test_measurement_scope_is_validated_without_claiming_attestation(self):
        directory = self.run_protocol()
        report = read_json(directory / "report.json")
        report["measurements"]["memory_limit_enforced"] = True
        write_json(directory / "report.json", report)
        self.refresh_manifest(directory, "report.json")
        with self.assertRaisesRegex(ContractError, "measurement scope"):
            self.verify(directory)

    def test_source_change_prevents_replay_under_new_code(self):
        directory = self.run_protocol()
        source = self.root / "noetloom/__init__.py"
        source.write_text(source.read_text() + "\n# changed source\n")
        with self.assertRaisesRegex(ContractError, "runtime source differs"):
            self.verify(directory)

    def test_oversized_policy_snapshot_cannot_expand_current_admission(self):
        directory = self.run_protocol()
        current = dict(self.policy)
        current["max_cases"] = 1
        write_json(self.root / "config/resource-policy.json", current)
        with self.assertRaisesRegex(ContractError, "query count"):
            self.verify(directory)

    def test_missing_extra_and_symlinked_payloads_fail(self):
        for mutation in ("missing", "extra", "symlink"):
            with self.subTest(mutation=mutation):
                directory = self.run_protocol()
                if mutation == "extra":
                    (directory / "extra.txt").write_text("unaccounted")
                elif mutation == "missing":
                    (directory / "manifest.json").unlink()
                else:
                    target = self.base / "report-copy.json"
                    shutil.copyfile(directory / "report.json", target)
                    (directory / "report.json").unlink()
                    (directory / "report.json").symlink_to(target)
                with self.assertRaises(ContractError):
                    self.verify(directory)

    def test_manifest_path_traversal_and_duplicate_inventory_fail(self):
        directory = self.run_protocol()
        original = read_json(directory / "manifest.json")
        for path in ("../report.json", original["artifacts"][1]["path"]):
            manifest = json.loads(json.dumps(original))
            if path.startswith("../"):
                manifest["artifacts"][0]["path"] = path
            else:
                manifest["artifacts"][0] = dict(manifest["artifacts"][1])
            write_json(directory / "manifest.json", manifest)
            with self.assertRaisesRegex(ContractError, "artifact paths"):
                self.verify(directory)

    def test_output_failure_leaves_incomplete_evidence_and_releases_lease(self):
        self.protocol["budget"]["max_output_bytes"] = 1024
        write_json(self.protocol_path, self.protocol)
        with self.assertRaisesRegex(StorageError, "output-byte"):
            self.run_protocol()
        self.assertFalse((self.cache / ".noetloom-run.lock").exists())
        directories = list(self.cache.iterdir())
        self.assertEqual(len(directories), 1)
        self.assertFalse((directories[0] / "manifest.json").exists())
        with self.assertRaisesRegex(ContractError, "partial runs"):
            self.verify(directories[0])

    def test_rejected_protocol_does_not_create_cache(self):
        self.protocol["training_performed"] = True
        write_json(self.protocol_path, self.protocol)
        with self.assertRaises(ContractError):
            self.run_protocol()
        self.assertFalse(self.cache.exists())

    def test_doctor_is_read_only(self):
        result = doctor(self.root, self.cache)
        self.assertFalse(result["writes_performed"])
        self.assertFalse(self.cache.exists())

    def test_explicit_ci_profile_is_recorded_and_replayed(self):
        result = self.invoke("run", self.protocol_path, "--cache", self.cache, "--profile", "ci-smoke")
        directory = Path(result["directory"])
        self.assertEqual(read_json(directory / "resource-policy.json")["profile"], "ci-smoke")
        self.assertEqual(self.invoke("verify-run", directory, "--profile", "ci-smoke")["harness_verdict"], "passed")

    def test_verified_failed_result_is_not_cli_success(self):
        self.protocol["bounded_memory_slots"] = 256
        write_json(self.protocol_path, self.protocol)
        directory = self.run_protocol()
        code, payload = self.cli("verify-run", directory)
        self.assertEqual(payload["harness_verdict"], "failed")
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "verified")

    def test_cli_validation_error_is_json_with_exit_two(self):
        code, error = self.cli("run", self.root / "missing.json", "--cache", self.cache)
        self.assertEqual(code, 2)
        self.assertEqual(error["code"], "validation_failed")

    def test_oversized_json_integer_is_a_structured_cli_error(self):
        self.protocol_path.write_text('{"integer":' + '9' * 5000 + '}')
        code, error = self.cli("run", self.protocol_path, "--cache", self.cache)
        self.assertEqual(code, 2)
        self.assertEqual(error["code"], "validation_failed")
        self.assertIn("invalid JSON", error["message"])
        self.assertFalse(self.cache.exists())

    def test_api_refuses_to_attest_to_a_different_source_checkout(self):
        (self.root / "noetloom/recall.py").write_text('raise RuntimeError("cannot evaluate")\n')
        with self.assertRaisesRegex(ContractError, "imported runtime root"):
            run_experiment(self.root, self.protocol_path, self.cache)
        with self.assertRaisesRegex(ContractError, "imported runtime root"):
            verify_run(self.root, self.cache / "not-a-run")
        self.assertFalse(self.cache.exists())

    def test_source_edit_after_import_requires_a_fresh_process(self):
        script = '''
from pathlib import Path
from noetloom.contracts import ContractError
from noetloom.runner import run_experiment
root = Path.cwd()
source = root / "noetloom/recall.py"
source.write_text(source.read_text() + "\\n# later edit\\n")
try:
    run_experiment(root, root / "protocol.json", root.parent / "cache")
except ContractError as error:
    assert "changed after import" in str(error), str(error)
else:
    raise AssertionError("executed after source drift")
'''
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=self.root,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.cache.exists())
