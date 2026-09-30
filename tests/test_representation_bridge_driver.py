from __future__ import annotations

import importlib.util
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from noetloom.contracts import ContractError, canonical_bytes, load_policy, read_json
from noetloom.storage import file_digest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("representation_bridge_driver_tests", ROOT / "scripts/representation_bridge.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def protocol():
    return read_json(ROOT / "experiments/EXP-0010/protocol.json")


def req(kind="fit", **kw):
    x = {"experiment": "EXP-0010", "kind": kind, "source": {}, "source_commit": "fixture",
         "stage": None, "observation": None, "arm": None, "condition": None,
         "seed": None, "original": None, "recovery": False, "retained_parent": None,
         "retained_parent_manifest_sha256": None}
    if kind == "fit":
        x.update(stage="one", observation="shift", arm="frozen_warm", condition="lr010", seed=14003,
                 retained_parent="/tmp/parent", retained_parent_manifest_sha256="a" * 64)
    elif kind in {"evaluate", "replay"}:
        x.update(original="/tmp/mixed")
    elif kind == "baseline":
        x.update(seed=14003, retained_parent="/tmp/parent", retained_parent_manifest_sha256="a" * 64)
    x.update(kw)
    return x


def record(cache, name, request, *, status="passed", acquired=True, usage=None):
    path = cache / ("representation-bridge-" + name)
    path.mkdir()
    request = copy.deepcopy(request)
    if request.get("original") and (Path(request["original"]) / "manifest.json").is_file():
        request["original_manifest_sha256"] = file_digest(Path(request["original"]) / "manifest.json")
    (path / "request.json").write_bytes(canonical_bytes(request))
    (path / "protocol.json").write_bytes(canonical_bytes(protocol()))
    if request["kind"] == "fit":
        (path / "fit.json").write_bytes(canonical_bytes({"acquisition": {"passed": acquired}}))
    if request["kind"] == "baseline":
        (path / "result.json").write_bytes(canonical_bytes({"old_competence": {"passed": acquired}}))
    result = {"schema_version": "noetloom.representation_bridge_run.v1", "status": status,
              "kind": request["kind"], "source": {}, "source_commit": "fixture",
              "usage": {"updates": 0, "affine_fit_examples": 0, "linear_systems": 0,
                        "presentations": 0, "forward_prefixes": 0, "seconds": 0, **(usage or {})},
              "artifacts": driver.supervisor.artifacts(path)}
    (path / "manifest.json").write_bytes(canonical_bytes(result))
    return path


def one_grid(cache, *, omit_last=False):
    p, parents = protocol(), {}
    for view in p["observations"]:
        for arm in p["arms"]:
            for seed in p["development_seeds"]:
                if omit_last and (view, arm, seed) == ("remix", "refit_reset", 14027):
                    continue
                parent = record(cache, f"one-{view}-{arm}-{seed}", req(observation=view, arm=arm, seed=seed))
                parents[(view, arm, seed)] = parent
                record(cache, f"replay-one-{view}-{arm}-{seed}", req("replay", original=str(parent)))
    return parents


class RepresentationBridgeDriverTests(unittest.TestCase):
    def test_frozen_protocol_rejects_new_rates_transforms_and_final_access(self):
        p = protocol()
        policy = load_policy(ROOT, "local-calibration")
        driver.validate_protocol(p, policy)
        for field in ("conditions", "observation_change", "final_access", "budget"):
            changed = copy.deepcopy(p)
            changed[field] = None
            with self.subTest(field=field), self.assertRaises(ContractError):
                driver.validate_protocol(changed, policy)

    def test_operation_argument_boundaries_and_observation_identity(self):
        p = protocol()
        driver.validate_request(req(), p)
        driver.validate_request(req(stage="mixed", original="/tmp/one"), p)
        driver.validate_request(req("replay", recovery=True), p)
        for bad in (req(observation="other"), req("preflight", arm="frozen_warm"),
                    req("evaluate", observation="shift"), req("replay", recovery=1),
                    req(stage="one", retained_parent="relative")):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                driver.validate_request(bad, p)
        a, b = req(), req(observation="remix")
        self.assertNotEqual(driver.key(a), driver.key(b))
        self.assertEqual(driver.key(req("baseline", seed=14003)), ("baseline", 14003))
        self.assertNotEqual(driver.key(req("replay", recovery=True)), driver.key(req("replay")))

    def test_reservations_distinguish_frozen_refit_and_solver_replay(self):
        p = protocol()
        frozen_run = driver.reservation(p, req(stage="one", arm="frozen_warm"))
        refit_run = driver.reservation(p, req(stage="one", arm="refit_warm"))
        self.assertEqual(frozen_run["updates"], 4096)
        self.assertEqual((frozen_run["affine_fit_examples"], frozen_run["linear_systems"]), (0, 0))
        self.assertEqual((refit_run["affine_fit_examples"], refit_run["linear_systems"]), (129 * 512, 129 * 4))
        self.assertEqual(driver.reservation(p, req("preflight"))["updates"], 64)
        self.assertEqual(driver.reservation(p, req("injection"))["updates"], 8)
        mixed = driver.reservation(p, req(stage="mixed", arm="refit_reset"))
        self.assertEqual((mixed["updates"], mixed["affine_fit_examples"], mixed["linear_systems"]),
                         (2048, 65 * 512, 65 * 4))
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            parent = record(cache, "fit", req(arm="refit_reset"))
            replay = driver.reservation(p, req("replay", original=str(parent)))
            self.assertEqual((replay["updates"], replay["affine_fit_examples"], replay["linear_systems"]),
                             (0, 129 * 512, 129 * 4))

    def test_every_baseline_and_ordinary_bound_replay_is_required(self):
        p = protocol()
        with tempfile.TemporaryDirectory() as temporary, patch.object(driver, "identity", return_value={}):
            cache = Path(temporary)
            for seed in p["development_seeds"]:
                parent = record(cache, f"baseline-{seed}", req("baseline", seed=seed))
                if seed != 14027:
                    record(cache, f"replay-baseline-{seed}", req("replay", original=str(parent)))
            with self.assertRaises(ContractError):
                driver.require_baselines(cache, p)
            record(cache, "recovery-baseline", req("replay", original=str(parent), recovery=True))
            with self.assertRaises(ContractError):
                driver.require_baselines(cache, p)
            record(cache, "replay-baseline-last", req("replay", original=str(parent)))
            driver.require_baselines(cache, p)
            manifest_path = parent / "manifest.json"
            value = read_json(manifest_path)
            value["extra"] = "changed manifest identity"
            manifest_path.write_bytes(canonical_bytes(value))
            with self.assertRaises(ContractError):
                driver.require_baselines(cache, p)

    def test_full_grid_barrier_then_independent_view_gates_and_exact_mixed_parent(self):
        p = protocol()
        with tempfile.TemporaryDirectory() as temporary, patch.object(driver, "identity", return_value={}):
            cache = Path(temporary)
            parents = one_grid(cache, omit_last=True)
            parent = parents[("shift", "frozen_warm", 14003)]
            mixed = req(stage="mixed", original=str(parent))
            self.assertIsNone(driver.selection(cache, p, "shift", "frozen_warm"))
            with self.assertRaises(ContractError):
                driver.require_mixed(cache, p, mixed)
            record(cache, "one-remix-refit_reset-14027", req(observation="remix", arm="refit_reset", seed=14027),
                   status="failed", acquired=False)
            self.assertEqual(driver.selection(cache, p, "shift", "frozen_warm"), "lr010")
            self.assertIsNone(driver.selection(cache, p, "remix", "refit_reset"))
            driver.require_mixed(cache, p, mixed)
            wrong = record(cache, "unregistered-copy", req())
            # Same fit identity in a different directory is a duplicate, never a substitute.
            with self.assertRaises(ContractError):
                driver.require_mixed(cache, p, req(stage="mixed", original=str(wrong)))

    def test_development_waits_for_every_mixed_seed_and_replay(self):
        p = protocol()
        with tempfile.TemporaryDirectory() as temporary, patch.object(driver, "identity", return_value={}):
            cache = Path(temporary)
            parents = one_grid(cache)
            for seed in p["development_seeds"]:
                parent = record(cache, f"mixed-{seed}", req(stage="mixed", seed=seed,
                                original=str(parents[("shift", "frozen_warm", seed)])))
                if seed != 14027:
                    record(cache, f"replay-mixed-{seed}", req("replay", original=str(parent)))
            evaluation = req("evaluate", original=str(parent))
            with self.assertRaises(ContractError):
                driver.require_evaluation(cache, p, evaluation)
            replay = record(cache, "replay-mixed-last", req("replay", original=str(parent)))
            driver.require_evaluation(cache, p, evaluation)
            (replay / "protocol.json").write_text("{}")
            with self.assertRaises(ContractError):
                driver.require_evaluation(cache, p, evaluation)

    def test_failed_attempts_cannot_repeat_and_remain_charged(self):
        p = protocol()
        with tempfile.TemporaryDirectory() as temporary, patch.object(driver, "identity", return_value={}):
            cache = Path(temporary)
            record(cache, "failed", req(), status="failed", acquired=False)
            with self.assertRaisesRegex(ContractError, "already attempted"):
                driver.admit(cache, p, req())
        with tempfile.TemporaryDirectory() as temporary, patch.object(driver, "identity", return_value={}):
            cache = Path(temporary)
            record(cache, "failed", req(), status="failed", acquired=False,
                   usage={"affine_fit_examples": p["budget"]["max_affine_fit_examples_total"]})
            with self.assertRaisesRegex(ContractError, "aggregate resource budget"):
                driver.admit(cache, p, req("preflight"))

    def test_current_manifest_refuses_artifact_or_source_corruption(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(driver, "identity", return_value={}):
            parent = record(Path(temporary), "fit", req())
            driver.manifest(parent)
            (parent / "fit.json").write_text("{}")
            with self.assertRaises(ContractError):
                driver.manifest(parent)


if __name__ == "__main__":
    unittest.main()
