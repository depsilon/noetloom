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
_spec = importlib.util.spec_from_file_location("affine_coordinates_driver_tests", ROOT / "scripts/affine_coordinates.py")
driver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(driver)


def protocol():
    return read_json(ROOT / "experiments/EXP-0009/protocol.json")


def request(kind="fit", **changes):
    value = {"experiment": "EXP-0009", "kind": kind, "stage": None, "arm": None,
             "condition": None, "seed": None, "source": {}, "original": None, "recovery": False}
    if kind == "fit":
        value.update(stage="one", arm="joint", condition="lr003", seed=13003)
    elif kind in {"evaluate", "replay"}:
        value.update(original="/prior/fit-run")
    value.update(changes)
    return value


def write_record(cache: Path, name: str, req: dict, *, status="passed", acquisition=True, usage=None):
    directory = cache / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "request.json").write_bytes(canonical_bytes(req))
    (directory / "manifest.json").write_bytes(canonical_bytes({
        "schema_version": "noetloom.affine_coordinates_run.v1", "status": status,
        "kind": req["kind"], "source": req.get("source", {}), "usage": usage or {}, "artifacts": []}))
    if req["kind"] == "fit":
        (directory / "fit.json").write_bytes(canonical_bytes({"acquisition": {"passed": acquisition}}))
    return directory


class AffineCoordinatesDriverTests(unittest.TestCase):
    def test_frozen_protocol_and_policy(self):
        original = protocol()
        driver.validate_protocol(original, load_policy(ROOT, "local-calibration"))
        mutations = []
        changed_solver = copy.deepcopy(original)
        changed_solver["solver"]["rcond"] = 1e-8
        mutations.append(changed_solver)
        changed_final = copy.deepcopy(original)
        changed_final["final_access"] = True
        mutations.append(changed_final)
        changed_budget = copy.deepcopy(original)
        changed_budget["budget"]["max_attempts"] += 1
        mutations.append(changed_budget)
        changed_root = copy.deepcopy(original)
        changed_root["unregistered"] = True
        mutations.append(changed_root)
        for changed in mutations:
            with self.subTest(change=changed):
                with self.assertRaises(ContractError):
                    driver.validate_protocol(changed, load_policy(ROOT, "local-calibration"))

    def test_fit_evaluation_and_replay_request_contracts(self):
        p = protocol()
        for arm in p["arms"]:
            for stage in ("one", "mixed"):
                req = request(stage=stage, arm=arm, original="/prior/one" if stage == "mixed" else None)
                driver.validate_request(req, p)
        driver.validate_request(request("evaluate", original="/prior/mixed"), p)
        driver.validate_request(request("replay", original="/prior/mixed"), p)
        invalid = [request(stage="tiny"), request(arm="reversible"), request(seed=13004),
                   request(stage="mixed"), request("evaluate", stage="mixed", original="/prior/mixed"),
                   request("preflight", original="/prior/run"), request("oracle")]
        for req in invalid:
            with self.subTest(request=req), self.assertRaises(ContractError):
                driver.validate_request(req, p)
        self.assertEqual(driver.key(request("evaluate", original="/a/mixed")),
                         driver.key(request("evaluate", original="/b/mixed")))
        self.assertNotEqual(driver.key(request("replay", original="/a/mixed", recovery=True)),
                            driver.key(request("replay", original="/a/mixed")))

    def test_failed_fit_identity_is_charged_and_solver_usage_has_total_caps(self):
        p = protocol()
        first = request(arm="refit")
        with tempfile.TemporaryDirectory() as temp, patch.object(driver, "identity", return_value={}), \
                patch.object(driver.supervisor, "artifacts", return_value=[]):
            cache = Path(temp)
            driver.admit(cache, p, first)
            write_record(cache, "affine-coordinates-fit-failed", first, status="failed",
                         usage={"updates": 4096, "affine_fit_examples": 66048, "linear_systems": 516})
            with self.assertRaisesRegex(ContractError, "already attempted"):
                driver.admit(cache, p, first)

        with tempfile.TemporaryDirectory() as temp, patch.object(driver, "identity", return_value={}), \
                patch.object(driver.supervisor, "artifacts", return_value=[]):
            cache = Path(temp)
            failed = request(arm="refit")
            write_record(cache, "affine-coordinates-prior-failed", failed, status="failed",
                         usage={"updates": 0, "affine_fit_examples": p["budget"]["max_affine_fit_examples_total"],
                                "linear_systems": 0, "presentations": 0, "forward_prefixes": 0, "seconds": 0})
            with self.assertRaisesRegex(ContractError, "aggregate resource budget exhausted"):
                driver.admit(cache, p, request("preflight"))

    def test_common_rate_requires_complete_both_rate_cross_product_and_parent_replays(self):
        p = protocol()
        with tempfile.TemporaryDirectory() as temp, patch.object(driver, "identity", return_value={}), \
                patch.object(driver.supervisor, "artifacts", return_value=[]):
            cache = Path(temp)
            parents = {}
            for condition in p["conditions"]:
                for seed in p["development_seeds"]:
                    passed = condition["name"] == "lr003"
                    req = request(stage="one", arm="joint", condition=condition["name"], seed=seed)
                    parents[(condition["name"], seed)] = write_record(
                        cache, f"affine-coordinates-one-{condition['name']}-{seed}", req,
                        status="passed" if passed else "failed", acquisition=passed)
                if condition["name"] == "lr003":
                    self.assertIsNone(driver.selection(cache, p, "joint"))
            self.assertEqual(driver.selection(cache, p, "joint"), "lr003")
            # Mixed fitting waits for all selected parents to be ordinarily replayed.
            for seed in p["development_seeds"][:-1]:
                write_record(cache, f"affine-coordinates-replay-{seed}",
                             request("replay", original=str(parents[("lr003", seed)])), status="passed")
            mixed = request(stage="mixed", arm="joint", condition="lr003", seed=p["development_seeds"][0],
                            original=str(parents[("lr003", p["development_seeds"][0])]))
            with self.assertRaisesRegex(ContractError, "every selected one-step parent"):
                driver.require_mixed(cache, p, mixed)
            seed = p["development_seeds"][-1]
            write_record(cache, f"affine-coordinates-replay-{seed}",
                         request("replay", original=str(parents[("lr003", seed)])), status="passed")
            self.assertIsNone(driver.require_mixed(cache, p, mixed))

    def test_evaluation_requires_acquired_and_replayed_mixed_grid(self):
        p = protocol()
        with tempfile.TemporaryDirectory() as temp, patch.object(driver, "identity", return_value={}), \
                patch.object(driver.supervisor, "artifacts", return_value=[]):
            cache = Path(temp)
            for condition in p["conditions"]:
                for seed in p["development_seeds"]:
                    ok = condition["name"] == "lr003"
                    write_record(cache, f"affine-coordinates-fit-one-{condition['name']}-{seed}",
                                 request(stage="one", arm="refit", condition=condition["name"], seed=seed),
                                 status="passed" if ok else "failed", acquisition=ok)
            mixed_parents = {}
            for seed in p["development_seeds"]:
                req = request(stage="mixed", arm="refit", condition="lr003", seed=seed,
                              original=f"/one/selected-{seed}")
                parent = write_record(cache, f"affine-coordinates-fit-mixed-{seed}", req, status="passed", acquisition=True)
                mixed_parents[seed] = parent
                write_record(cache, f"affine-coordinates-replay-mixed-{seed}", request("replay", original=str(parent)), status="passed")
            evaluation = request("evaluate", original=str(mixed_parents[p["development_seeds"][0]]))
            self.assertIsNone(driver.require_evaluation(cache, p, evaluation))
            last = p["development_seeds"][-1]
            (cache / f"affine-coordinates-replay-mixed-{last}" / "manifest.json").unlink()
            with self.assertRaisesRegex(ContractError, "every selected mixed parent"):
                driver.require_evaluation(cache, p, evaluation)

    def test_reservations_cover_stage_refits_and_replay_solves(self):
        p = protocol()
        self.assertEqual(driver.reservation(p, request(stage="one", arm="joint"))["updates"], 4096)
        one = driver.reservation(p, request(stage="one", arm="refit"))
        self.assertEqual((one["updates"], one["affine_fit_examples"], one["linear_systems"]),
                         (4096, 129 * 512, 129 * 4))
        mixed = driver.reservation(p, request(stage="mixed", arm="refit"))
        self.assertEqual((mixed["updates"], mixed["affine_fit_examples"], mixed["linear_systems"]),
                         (2048, 65 * 512, 65 * 4))
        self.assertEqual(driver.reservation(p, request("preflight"))["updates"], 32)
        self.assertEqual(driver.reservation(p, request("preflight"))["affine_fit_examples"], 512)
        self.assertEqual(driver.reservation(p, request("preflight"))["linear_systems"], 16)
        self.assertEqual(driver.reservation(p, request("injection"))["updates"], 8)
        with tempfile.TemporaryDirectory() as temp:
            original = Path(temp) / "fit-run"
            original.mkdir()
            (original / "request.json").write_bytes(canonical_bytes(request(stage="mixed", arm="refit")))
            replay = driver.reservation(p, request("replay", original=str(original)))
            self.assertEqual((replay["updates"], replay["affine_fit_examples"], replay["linear_systems"]),
                             (0, 65 * 512, 65 * 4))
        evaluation = driver.reservation(p, request("evaluate", original="/fit/mixed"))
        self.assertEqual((evaluation["updates"], evaluation["affine_fit_examples"], evaluation["linear_systems"]),
                         (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
