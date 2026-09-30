from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from noetloom.contracts import ContractError, canonical_bytes, read_json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("state_representation_driver_tests", ROOT / "scripts/state_representation.py")
driver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(driver)


def protocol():
    return read_json(ROOT / "experiments/EXP-0007/protocol.json")


def request(kind="fit", **changes):
    values = {"experiment": "EXP-0007", "kind": kind, "observation": "aligned", "arm": None,
              "condition": None, "seed": None, "original": None, "recovery": False, "source": {}}
    if kind == "fit":
        values.update(arm="latent", condition="lr003", seed=11003)
    elif kind == "injection":
        values.update(arm="latent", condition="lr003", seed=180797)
    elif kind in {"transfer", "replay"}:
        values.update(original="fit-original")
    values.update(changes)
    return values


def ledger_entry(cache: Path, name: str, req: dict, *, status="passed", acquisition=True):
    directory = cache / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "request.json").write_bytes(canonical_bytes(req))
    manifest = {"schema_version": "noetloom.state_rep_run.v1", "status": status,
                "kind": req["kind"], "source": req.get("source", {}), "artifacts": []}
    (directory / "manifest.json").write_bytes(canonical_bytes(manifest))
    if req["kind"] == "fit":
        (directory / "fit.json").write_bytes(canonical_bytes({"acquisition_passed": acquisition}))
    return directory


class StateRepresentationDriverTests(unittest.TestCase):
    def test_validate_request_rejects_unregistered_and_malformed_identities(self):
        p = protocol()
        good = request()
        bad_requests = [
            {**good, "kind": "final"},
            {**good, "kind": "mystery"},
            {**good, "seed": True},
            {**good, "arm": None},
            {**good, "condition": None},
            {**good, "original": "prior-run"},
            {**request("replay"), "original": None},
            {**good, "observation": "final"},
        ]
        for invalid in bad_requests:
            with self.subTest(kind=invalid.get("kind"), seed=invalid.get("seed")):
                with self.assertRaises(ContractError):
                    driver.validate_request(invalid, p)

    def test_one_valid_request_for_each_admitted_kind(self):
        p = protocol()
        valid = [request("preflight"), request("injection"), request("fit"), request("affine"),
                 request("transfer"), request("replay")]
        self.assertEqual({item["kind"] for item in valid}, set(driver.KINDS))
        for item in valid:
            with self.subTest(kind=item["kind"]):
                driver.validate_request(item, p)

    def test_admit_rejects_duplicate_failed_or_incomplete_fit_and_accepts_fresh_fit(self):
        p = protocol()
        req = request()
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            driver.admit(cache, p, req)
            ledger_entry(cache, "state-repr-aligned-fit-failed", req, status="failed")
            with self.assertRaisesRegex(ContractError, "already attempted"):
                driver.admit(cache, p, req)
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            directory = cache / "state-repr-aligned-fit-incomplete"
            directory.mkdir()
            (directory / "request.json").write_bytes(canonical_bytes(req))
            with self.assertRaisesRegex(ContractError, "already attempted"):
                driver.admit(cache, p, req)
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            self.assertIsNone(driver.admit(cache, p, req))

    def test_attempt_ceiling_and_nonlinear_gate_use_registered_budget_and_acquisition(self):
        p = protocol()
        req = request("fit")
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            # The attempt ceiling is checked before any resource-ledger details.
            for index in range(p["budget"]["max_attempts"]):
                ledger_entry(cache, f"state-repr-old-{index:03d}",
                             {"experiment": "EXP-0007", "kind": "preflight", "observation": "aligned"})
            with self.assertRaisesRegex(ContractError, "attempt ceiling"):
                driver.admit(cache, p, req)
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            nonlinear = {**req, "observation": "nonlinear"}
            with patch.object(driver, "identity", return_value={}):
                with self.assertRaisesRegex(ContractError, "aligned seeds"):
                    driver.admit(cache, p, nonlinear)
                self.assertIsNone(driver.admit(cache, p, req))

    def test_selection_requires_all_seeds_at_one_acquired_condition(self):
        p = protocol()
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            with patch.object(driver, "identity", return_value={}), \
                 patch.object(driver.supervisor, "artifacts", return_value=[]):
                for seed in p["development_seeds"]:
                    ledger_entry(cache, f"state-repr-fit-{seed}",
                                 request("fit", seed=seed, source={}))
                self.assertEqual(driver.selection(cache, p, "aligned", "latent"), "lr003")
                failed = cache / f"state-repr-fit-{p['development_seeds'][-1]}"
                (failed / "fit.json").write_bytes(canonical_bytes({"acquisition_passed": False}))
                self.assertIsNone(driver.selection(cache, p, "aligned", "latent"))

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            with patch.object(driver, "identity", return_value={}), \
                 patch.object(driver.supervisor, "artifacts", return_value=[]):
                for index, seed in enumerate(p["development_seeds"]):
                    condition = "lr003" if index < 2 else "lr010"
                    ledger_entry(cache, f"state-repr-mixed-{seed}",
                                 request("fit", seed=seed, condition=condition, source={}))
                self.assertIsNone(driver.selection(cache, p, "aligned", "latent"))

    def test_require_transfer_demands_acquisition_matching_original_and_successful_replay(self):
        p = protocol()
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            original_req = request("fit", source={})
            original = ledger_entry(cache, "state-repr-original-fit", original_req)
            with patch.object(driver, "identity", return_value={}), \
                 patch.object(driver.supervisor, "artifacts", return_value=[]):
                with self.assertRaisesRegex(ContractError, "every arm seed"):
                    driver.require_transfer(cache, p, original)

                for seed in p["development_seeds"]:
                    ledger_entry(cache, f"state-repr-acquired-{seed}",
                                 request("fit", seed=seed, source={}))
                with self.assertRaisesRegex(ContractError, "complete measurement"):
                    driver.require_transfer(cache, p, original)

                original_req["condition"] = "lr010"
                (original / "request.json").write_bytes(canonical_bytes(original_req))
                with self.assertRaisesRegex(ContractError, "every arm seed"):
                    driver.require_transfer(cache, p, original)
                original_req["condition"] = "lr003"
                (original / "request.json").write_bytes(canonical_bytes(original_req))

                replay_req = request("replay", original=str(original), source={})
                replay = cache / "state-repr-replay-incomplete"
                replay.mkdir()
                (replay / "request.json").write_bytes(canonical_bytes(replay_req))
                with self.assertRaisesRegex(ContractError, "complete measurement"):
                    driver.require_transfer(cache, p, original)
                (replay / "manifest.json").write_bytes(canonical_bytes({
                    "schema_version": "noetloom.state_rep_run.v1", "status": "failed", "source": {}, "artifacts": []}))
                with self.assertRaisesRegex(ContractError, "complete measurement"):
                    driver.require_transfer(cache, p, original)
                (replay / "manifest.json").write_bytes(canonical_bytes({
                    "schema_version": "noetloom.state_rep_run.v1", "status": "passed", "source": {}, "artifacts": []}))
                self.assertIsNone(driver.require_transfer(cache, p, original))

    def test_manifest_rejects_tampered_artifacts_and_mismatched_source(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            artifacts = [{"path": "result.json", "bytes": 8, "sha256": "abc"}]
            value = {"schema_version": "noetloom.state_rep_run.v1", "status": "passed",
                     "source": {"files": ["current"]}, "artifacts": artifacts}
            path = directory / "manifest.json"
            path.write_bytes(canonical_bytes(value))
            with patch.object(driver, "identity", return_value=value["source"]), \
                 patch.object(driver.supervisor, "artifacts", return_value=artifacts):
                self.assertEqual(driver.manifest(directory), value)
                path.write_bytes(canonical_bytes({**value, "artifacts": []}))
                with self.assertRaisesRegex(ContractError, "artifact bytes"):
                    driver.manifest(directory)
                path.write_bytes(canonical_bytes({**value, "source": {"files": ["old"]}}))
                with self.assertRaisesRegex(ContractError, "source"):
                    driver.manifest(directory)


if __name__ == "__main__":
    unittest.main()
