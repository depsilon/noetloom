from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from noetloom.contracts import ContractError, canonical_bytes, read_json
from noetloom.storage import file_digest
from noetloom import transition_diagnostics as diagnostics
from noetloom.transition_data import score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
_driver_spec = importlib.util.spec_from_file_location("transition_diagnostics_driver_tests", ROOT / "scripts/transition_diagnostics.py")
driver = importlib.util.module_from_spec(_driver_spec)
_driver_spec.loader.exec_module(driver)


def protocol() -> dict:
    return read_json(ROOT / "experiments/EXP-0007/diagnostics.json")


def evidence() -> dict:
    return read_json(ROOT / "docs/evidence/N-008-2026-09-30.json")


class TransitionDiagnosticsTests(unittest.TestCase):
    def test_saved_transfer_rows_envelope_is_scored_without_schema_translation(self):
        row = {"initial": [0] * 8, "actions": [0, 1], "targets": [[1] * 8, [0] * 8], "family": "synthetic"}
        data = {"rows": [row]}
        saved = {"logits": [[[1.0] * 8, [-1.0] * 8]], "predictions": [[0] * 8], "scored": score([row], [[0] * 8])}
        record = {"run": "synthetic", "kind": "transfer", "arm": "shared_transition", "seed": 1,
                  "stage": "development_transfer", "condition": "lr003", "selected_step": 1}
        usage = {"scored_trajectories": 0, "scored_prefixes": 0}
        with patch.object(diagnostics, "load", return_value=data), patch.object(diagnostics, "read_json", return_value=saved):
            result = diagnostics.audit_saved(Path("/unused"), [record], usage)
        self.assertEqual(result[0]["splits"]["development"]["all"]["all_prefix_exact"], 1)
        self.assertEqual(usage, {"scored_trajectories": 1, "scored_prefixes": 2})
        self.assertEqual(diagnostics.historical_rows(data, "transfer", "development"), [row])
        with self.assertRaisesRegex(ContractError, "envelope"):
            diagnostics.historical_rows({"training": [row]}, "transfer", "development")

    def test_repair_preserves_total_admission_and_original_registration(self):
        repaired = read_json(ROOT / "experiments/EXP-0007/diagnostics-repair.json")
        diagnostics.validate_registration(repaired)
        self.assertEqual(repaired["amendment"]["original_protocol_sha256"], file_digest(ROOT / "experiments/EXP-0007/diagnostics.json"))
        original = protocol()
        restored = copy.deepcopy(repaired)
        restored.pop("amendment")
        restored["budget"].update(max_runs=1, max_replays=3)
        self.assertEqual(restored, original)

    def test_registration_is_exact(self):
        expected = protocol()
        diagnostics.validate_registration(expected)
        mutations = []
        for key, value in (("final_access", True), ("external_pretrained_components", ["foreign teacher"]),
                           ("seeds", [9103, 9209, 9312]), ("budget", {**expected["budget"], "max_runs": 2}),
                           ("unknown", True), ("historical_evidence_sha256", "0" * 64)):
            altered = copy.deepcopy(expected)
            altered[key] = value
            mutations.append(altered)
        for altered in mutations:
            with self.subTest(change=next(k for k in altered if altered[k] != expected.get(k))):
                with self.assertRaises(ContractError):
                    diagnostics.validate_registration(altered)

    def test_real_registry_has_exact_fit_transfer_and_snapshot_coverage(self):
        records = diagnostics.input_registry(evidence())
        self.assertEqual(len(records), 27)
        fits = [row for row in records if row["kind"] == "fit"]
        transfers = [row for row in records if row["kind"] == "transfer"]
        snapshots = [row for row in records if row["snapshot_sha256"] is not None]
        self.assertEqual((len(fits), len(transfers), len(snapshots)), (24, 3, 6))
        for subset in (fits, transfers, snapshots):
            by_seed = {seed: [row for row in subset if row["seed"] == seed]
                       for seed in protocol()["seeds"]}
            self.assertTrue(all(by_seed.values()))
        for seed in protocol()["seeds"]:
            self.assertEqual(sum(row["seed"] == seed and row["stage"] == "one" for row in snapshots), 1)
            self.assertEqual(sum(row["seed"] == seed and row["stage"] == "mixed" for row in snapshots), 1)

        missing = copy.deepcopy(evidence())
        missing["fit_records"].pop()
        duplicate = copy.deepcopy(evidence())
        duplicate["development_transfer"][0]["run"] = duplicate["fit_records"][0]["basename"]
        unacquired = copy.deepcopy(evidence())
        row = next(row for row in unacquired["fit_records"]
                   if row["arm"] == "shared_transition" and row["stage"] in {"one", "mixed"})
        row["acquisition"]["passed"] = False
        for altered in (missing, duplicate, unacquired):
            with self.assertRaises(ContractError):
                diagnostics.input_registry(altered)

    def test_validate_inputs_checks_copied_bytes_and_provenance(self):
        record = {"run": "synthetic-run", "kind": "fit", "arm": "direct", "seed": 42, "stage": "one",
                  "condition": "lr003", "selected_step": 7, "manifest_sha256": "", "files": {"data": "data.json"},
                  "snapshot_sha256": None}
        protocol_value = {"historical_source_commit": "source-commit"}
        evidence_value = {"source": {"commit": "source-commit"}}
        source_payloads = {"data": b'{"synthetic":true}\n'}
        data_artifact = {"path": "data.json", "bytes": len(source_payloads["data"]),
                         "sha256": hashlib.sha256(source_payloads["data"]).hexdigest()}
        manifest = {"source_commit": "source-commit", "status": "passed", "source": evidence_value["source"],
                    "artifacts": [data_artifact]}
        manifest_bytes = canonical_bytes(manifest)
        record["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        original_manifest_sha256 = record["manifest_sha256"]
        expected_registry = [record]

        def write_inputs(directory: Path, *, changed_data=False, changed_manifest=False, wrong_commit=False,
                         wrong_status=False, snapshot_hash=None):
            payload = b'{"synthetic":false}\n' if changed_data else source_payloads["data"]
            local_manifest = copy.deepcopy(manifest)
            if wrong_commit:
                local_manifest["source_commit"] = "other-commit"
            if wrong_status:
                local_manifest["status"] = "failed"
            if changed_manifest:
                local_manifest["extra"] = "changed"
            if snapshot_hash is not None:
                snapshot_bytes = b"snapshot"
                snapshot_artifact = {"path": "selected.json", "bytes": len(snapshot_bytes),
                                     "sha256": hashlib.sha256(snapshot_bytes).hexdigest()}
                local_manifest["artifacts"].append(snapshot_artifact)
                (directory / diagnostics.copied_name(0, "snapshot")).write_bytes(snapshot_bytes)
                record["files"]["snapshot"] = "selected.json"
                record["snapshot_sha256"] = snapshot_hash
            manifest_to_write = canonical_bytes(local_manifest) if changed_manifest or wrong_commit or wrong_status or snapshot_hash is not None else manifest_bytes
            if wrong_commit or wrong_status:
                record["manifest_sha256"] = hashlib.sha256(manifest_to_write).hexdigest()
            if snapshot_hash is not None:
                record["manifest_sha256"] = hashlib.sha256(manifest_to_write).hexdigest()
            (directory / diagnostics.copied_name(0, "manifest")).write_bytes(manifest_to_write)
            (directory / diagnostics.copied_name(0, "data")).write_bytes(payload)

        cases = ({}, {"changed_data": True}, {"changed_manifest": True}, {"wrong_commit": True},
                 {"wrong_status": True}, {"snapshot_hash": "0" * 64})
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                record["files"] = {"data": "data.json"}
                record["snapshot_sha256"] = None
                record["manifest_sha256"] = original_manifest_sha256
                write_inputs(directory, **case)
                with patch.object(diagnostics, "input_registry", return_value=expected_registry):
                    if case:
                        expected_error = (
                            "input bytes differ" if case.get("changed_data") else
                            "manifest differs" if case.get("changed_manifest") else
                            "source or execution status differs" if case.get("wrong_commit") or case.get("wrong_status") else
                            "selected snapshot differs"
                        )
                        with self.assertRaisesRegex(ContractError, expected_error):
                            diagnostics.validate_inputs(directory, expected_registry, protocol_value, evidence_value)
                    else:
                        diagnostics.validate_inputs(directory, expected_registry, protocol_value, evidence_value)

    def test_copy_bounded_checks_admission_before_creating_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / "run"
            directory.mkdir()
            source = root / "source.json"
            source.write_bytes(b"small")
            target = directory / "copy.json"
            with patch.object(diagnostics, "tree_bytes", return_value=100):
                with self.assertRaises(ContractError):
                    diagnostics.copy_bounded(source, target, directory, 100)
            self.assertFalse(target.exists())
            with patch.object(diagnostics, "tree_bytes", return_value=0):
                diagnostics.copy_bounded(source, target, directory, 65541)
                with self.assertRaises(FileExistsError):
                    diagnostics.copy_bounded(source, target, directory, 65541)

    def _make_attempt(self, cache: Path, index: int, kind: str, *, seconds=1.0, manifest=True, size=1):
        directory = cache / f"transition-diagnostic-{index}"
        directory.mkdir()
        (directory / "request.json").write_bytes(canonical_bytes({"kind": kind}))
        if manifest:
            (directory / "manifest.json").write_bytes(canonical_bytes({"seconds": seconds}))
        (directory / "payload").write_bytes(b"x" * size)
        return directory

    def test_admit_enforces_attempt_run_replay_time_and_disk_budgets(self):
        limits = {"max_attempts": 4, "max_runs": 1, "max_replays": 3, "max_wall_seconds_per_run": 120,
                  "max_wall_seconds_total": 480, "max_output_bytes_per_run": 10,
                  "max_artifact_bytes_total": 40}
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            driver.admit(cache, {"budget": limits}, "run")

            with self.assertRaises(ContractError):
                driver.admit(cache, {"budget": limits}, "other")

            self._make_attempt(cache, 1, "run")
            with self.assertRaises(ContractError):
                driver.admit(cache, {"budget": limits}, "run")

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            for i in range(3):
                self._make_attempt(cache, i, "replay")
            with self.assertRaises(ContractError):
                driver.admit(cache, {"budget": limits}, "replay")

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            for i in range(4):
                self._make_attempt(cache, i, "replay")
            with self.assertRaises(ContractError):
                driver.admit(cache, {"budget": limits}, "run")

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            self._make_attempt(cache, 1, "replay")
            attempt_limits = {**limits, "max_attempts": 1}
            with self.assertRaisesRegex(ContractError, "attempt ceiling"):
                driver.admit(cache, {"budget": attempt_limits}, "run")

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            wall_limits = {**limits, "max_wall_seconds_total": 400}
            for i in range(3):
                self._make_attempt(cache, i, "replay", manifest=False)
            with patch.object(driver, "tree_bytes", return_value=0):
                with self.assertRaisesRegex(ContractError, "total budget exhausted"):
                    driver.admit(cache, {"budget": wall_limits}, "run")
                boundary_limits = {**limits, "max_wall_seconds_total": 480}
                self.assertIsNone(driver.admit(cache, {"budget": boundary_limits}, "run"))

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            self._make_attempt(cache, 1, "replay", size=1)
            with patch.object(driver, "tree_bytes", return_value=40):
                with self.assertRaisesRegex(ContractError, "total budget exhausted"):
                    driver.admit(cache, {"budget": limits}, "run")

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            self.assertIsNone(driver.admit(cache, {"budget": limits}, "run"))

    def test_validated_run_rejects_status_source_and_inventory_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            current_source = {"files": [{"path": "module.py", "sha256": "abc"}]}
            current_artifacts = [{"path": "result.json", "bytes": 2, "sha256": "de"}]
            manifest = {"schema_version": "noetloom.transition_diagnostic_run.v1", "status": "passed",
                        "source": current_source, "artifacts": current_artifacts}
            path = directory / "manifest.json"
            path.write_bytes(canonical_bytes(manifest))
            with patch.object(driver, "identity", return_value=current_source), \
                 patch.object(driver.supervisor, "artifacts", return_value=current_artifacts):
                self.assertEqual(driver.validated_run(directory), manifest)
                for altered in ({**manifest, "status": "failed"},
                                {**manifest, "source": {"files": []}},
                                {**manifest, "artifacts": []}):
                    path.write_bytes(canonical_bytes(altered))
                    with self.assertRaises(ContractError):
                        driver.validated_run(directory)


if __name__ == "__main__":
    unittest.main()
