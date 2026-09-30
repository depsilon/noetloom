from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from noetloom.contracts import ContractError, canonical_bytes, load_policy, read_json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("coordinates_driver_tests", ROOT / "scripts/coordinates.py")
driver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(driver)


def protocol():
    return read_json(ROOT / "experiments/EXP-0008/protocol.json")


def request(kind="fit", **changes):
    value = {"experiment": "EXP-0008", "kind": kind, "stage": None, "arm": None,
             "condition": None, "seed": None, "source": {}, "original": None,
             "recovery": False}
    if kind == "fit":
        value.update(stage="one", arm="latent", condition="lr003", seed=12003)
    elif kind == "replay":
        value.update(original="/prior/fit-run")
    value.update(changes)
    return value


def write_record(cache: Path, name: str, req: dict, *, status="failed", usage=None,
                 acquisition=True):
    directory = cache / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "request.json").write_bytes(canonical_bytes(req))
    (directory / "manifest.json").write_bytes(canonical_bytes({
        "schema_version": "noetloom.coordinates_run.v1", "status": status,
        "kind": req["kind"], "source": req.get("source", {}),
        "usage": usage or {}, "artifacts": []}))
    if req["kind"] == "fit":
        (directory / "fit.json").write_bytes(canonical_bytes({"acquisition": {"passed": acquisition}}))
    return directory


class CoordinatesDriverTests(unittest.TestCase):
    def test_frozen_protocol_and_local_calibration_policy(self):
        original = protocol()
        policy = load_policy(ROOT, "local-calibration")
        driver.validate_protocol(original, policy)
        mutations = []
        changed_rate = copy.deepcopy(original)
        changed_rate["conditions"][0]["rate"] = 0.004
        mutations.append(changed_rate)
        changed_final = copy.deepcopy(original)
        changed_final["final_access"] = True
        mutations.append(changed_final)
        changed_budget = copy.deepcopy(original)
        changed_budget["budget"]["max_attempts"] += 1
        mutations.append(changed_budget)
        extra_root = copy.deepcopy(original)
        extra_root["unregistered"] = "value"
        mutations.append(extra_root)
        for changed in mutations:
            with self.subTest(change=changed):
                with self.assertRaises(ContractError):
                    driver.validate_protocol(changed, policy)

    def test_fit_stage_parent_and_seed_contracts(self):
        p = protocol()
        for stage in ("tiny", "one"):
            for arm in p["arms"]:
                driver.validate_request(request(stage=stage, arm=arm), p)
        driver.validate_request(request(stage="mixed", original="/prior/one-run"), p)
        for invalid in (request(stage="mixed"), request(kind="final"),
                        request(seed=12004)):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ContractError):
                    driver.validate_request(invalid, p)

    def test_failed_identity_cannot_retry_and_failed_usage_remains_charged(self):
        p = protocol()
        first = request()
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            driver.admit(cache, p, first)
            write_record(cache, "coordinates-fit-failed", first, usage={"updates": 0})
            with self.assertRaisesRegex(ContractError, "already attempted"):
                driver.admit(cache, p, first)

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            failed = request(stage="tiny", seed=12009)
            write_record(cache, "coordinates-prior-failed", failed,
                         usage={"updates": 4200, "presentations": 0,
                                "forward_prefixes": 0, "seconds": 0})
            limited = copy.deepcopy(p)
            limited["budget"]["max_gradient_updates_total"] = 4200
            with self.assertRaisesRegex(ContractError, "aggregate resource budget exhausted"):
                driver.admit(cache, limited, request(kind="preflight"))

    def test_replay_identity_uses_basename_and_recovery_flag(self):
        ordinary = request("replay", original="/first/location/fit-run", recovery=False)
        same_basename = request("replay", original="/second/location/fit-run", recovery=False)
        recovery = request("replay", original="/second/location/fit-run", recovery=True)
        self.assertEqual(driver.key(ordinary), driver.key(same_basename))
        self.assertNotEqual(driver.key(ordinary), driver.key(recovery))

    def test_common_condition_and_all_parent_replays_gate_mixed(self):
        p = protocol()
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            with patch.object(driver, "identity", return_value={}), \
                 patch.object(driver.supervisor, "artifacts", return_value=[]):
                parent_dirs = {}
                for seed in p["development_seeds"]:
                    parent_dirs[seed] = write_record(cache, f"coordinates-one-{seed}",
                        request(source={}, seed=seed), status="passed")
                self.assertIsNone(driver.selection(cache, p, "latent"))
                for seed in p["development_seeds"]:
                    write_record(cache, f"coordinates-one-lr010-{seed}",
                        request(source={}, seed=seed, condition="lr010"),
                        status="failed", acquisition=False)
                self.assertEqual(driver.selection(cache, p, "latent"), "lr003")
                failing = parent_dirs[p["development_seeds"][-1]] / "fit.json"
                failing.write_bytes(canonical_bytes({"acquisition": {"passed": False}}))
                self.assertIsNone(driver.selection(cache, p, "latent"))
                failing.write_bytes(canonical_bytes({"acquisition": {"passed": True}}))

                parent = parent_dirs[p["development_seeds"][0]]
                mixed = request(stage="mixed", seed=p["development_seeds"][0],
                                original=str(parent), source={})
                for seed in p["development_seeds"][:-1]:
                    write_record(cache, f"coordinates-replay-{seed}",
                        request("replay", original=str(parent_dirs[seed]), source={}), status="passed")
                with self.assertRaisesRegex(ContractError, "every one-step parent"):
                    driver.require_mixed(cache, p, mixed)
                seed = p["development_seeds"][-1]
                write_record(cache, f"coordinates-replay-{seed}",
                    request("replay", original=str(parent_dirs[seed]), source={}), status="passed")
                self.assertIsNone(driver.require_mixed(cache, p, mixed))

    def test_reservation_counts_fit_and_replay_perturbations_but_not_oracle_updates(self):
        p = protocol()
        tiny = driver.reservation(p, request(stage="tiny"))
        one = driver.reservation(p, request(stage="one"))
        reversible = driver.reservation(p, request(stage="one", arm="reversible"))
        mixed = driver.reservation(p, request(stage="mixed"))
        self.assertEqual(tiny["updates"], 2048 + 3 * 4)
        self.assertEqual(one["updates"], 4096 + 3 * 4)
        self.assertEqual(reversible["updates"], 4096 + 3 * 2)
        self.assertEqual(mixed["updates"], 2048)

        with tempfile.TemporaryDirectory() as temp:
            original = Path(temp) / "fit-run"
            original.mkdir()
            (original / "request.json").write_bytes(canonical_bytes(request(stage="one")))
            replay = driver.reservation(p, request("replay", original=str(original)))
            self.assertEqual(replay["updates"], 3 * 4)
        self.assertEqual(driver.reservation(p, request("oracle"))["updates"], 0)


if __name__ == "__main__":
    unittest.main()
