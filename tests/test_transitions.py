from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from noetloom.contracts import ContractError, canonical_bytes, load_policy, read_json
from noetloom.transition_contracts import acquisition_gate, select_measurement, validate_protocol
from noetloom.transition_data import audit, generate, partition, render, score, simulate, training_words, transfer, transfer_words, transform
from noetloom.transition_model import advance, forward_ops, parameter_count, scalar_forward, validate_snapshot
from noetloom.storage import file_digest
from noetloom.transition_worker import replay_transfer, Work

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("transition_driver_tests", ROOT / "scripts/transitions.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def protocol():
    return read_json(ROOT / "experiments/EXP-0006/protocol.json")


def measurement(p, stage, accuracy=1.0, loss=0.2, step=1):
    result = {"step": step}
    for name, rows in generate(p, stage).items():
        metrics = score(rows, [row["targets"][-1] for row in rows])
        for item in metrics.values():
            item["exact_accuracy"] = accuracy
        result[name] = {"loss": loss, "scored": metrics}
    return result


class TransitionTests(unittest.TestCase):
    def test_exact_registration_and_resource_profile(self):
        p = protocol()
        validate_protocol(p, load_policy(ROOT, "local-calibration"))
        for key, value in (("unknown", True), ("external_pretrained_components", ["teacher"]), ("development_seeds", [1, 2, 3])):
            wrong = copy.deepcopy(p)
            wrong[key] = value
            with self.assertRaises(ContractError):
                validate_protocol(wrong, load_policy(ROOT, "local-calibration"))
        with self.assertRaises(ContractError):
            validate_protocol(p, load_policy(ROOT))

    def test_partition_audit_has_no_effective_or_latent_overlap(self):
        p = protocol()
        result = audit(p)
        self.assertEqual(result["actual_input_prefix_audit"]["conflicting_signatures"], 0)
        self.assertFalse(any(result["latent_trajectory_overlaps"].values()))
        self.assertEqual(len(result["order_witnesses"]), 6)
        self.assertEqual(result["structural_word_counts"]["final"], {"novel_pair": 2, "longer4": 54, "novel4": 56, "longer6": 486})
        counts = {s: {k: len(v) for k, v in generate(p, s).items()} for s in p["stages"]}
        self.assertEqual(counts, {"tiny": {"training": 32, "validation": 0}, "one": {"training": 640, "validation": 128}, "mixed": {"training": 896, "validation": 256}})
        states = partition(p["data"])
        self.assertEqual(len(set(sum(states.values(), []))), 256)
        for values in states.values():
            for bit in range(8):
                self.assertEqual(sum((state >> bit) & 1 for state in values), len(values) // 2)

    def test_final_net_computations_exclude_all_development_subwords(self):
        config = protocol()["data"]
        trained = {transform(config, word) for length in (1, 2, 3) for word in training_words(config, length)}
        dev = {transform(config, word[start:end]) for family in ("novel_pair", "longer4", "novel4", "longer6")
               for word in transfer_words(config, "development", family)
               for start in range(len(word)) for end in range(start + 1, len(word) + 1)}
        for family in ("novel_pair", "longer4", "novel4", "longer6"):
            for word in transfer_words(config, "final", family):
                self.assertNotIn(transform(config, word), trained | dev)

    def test_canonical_transform_matches_sequential_world_on_all_states(self):
        config = protocol()["data"]
        for actions in ((0,), (1, 2), (3, 1, 0), (2, 0, 3, 1, 2, 3)):
            permutation, flips = transform(config, actions)
            for state in range(256):
                bits = [(state >> bit) & 1 for bit in range(8)]
                self.assertEqual(simulate(config, bits, actions)[-1], [bits[i] ^ flip for i, flip in zip(permutation, flips)])

    def test_no_final_render_during_development_or_audit(self):
        p = protocol()
        forbidden = set(partition(p["data"])["final"])
        def guarded(config, state, word, family):
            self.assertNotIn(state, forbidden)
            return render(config, state, word, family)
        with patch("noetloom.transition_data.render", side_effect=guarded):
            audit(p)
            for stage in p["stages"]:
                generate(p, stage)
        with self.assertRaises(ContractError):
            transfer(p, "final")

    def test_copy_cannot_hide_changed_bit_failure(self):
        rows = generate(protocol(), "mixed")["validation"]
        result = score(rows, [row["initial"] for row in rows])
        self.assertEqual(result["all"]["correct_changed_bits"], 0)
        self.assertEqual(result["all"]["changed_bit_accuracy"], 0)
        self.assertGreater(result["all"]["changed_bits"], 0)
        self.assertLess(result["all"]["exact_accuracy"], 0.1)

    def test_selection_requires_all_slices_and_keeps_failure(self):
        p = protocol()
        rows = [measurement(p, "mixed", loss=0.3, step=1), measurement(p, "mixed", loss=0.1, step=2)]
        rows[1]["validation"]["scored"]["length/3"]["changed_bit_accuracy"] = 0.94
        self.assertFalse(acquisition_gate("mixed", rows[1], p)["passed"])
        index, result = select_measurement("mixed", rows, p)
        self.assertEqual(index, 0)
        self.assertTrue(result["passed"])
        rows[0]["training"]["scored"].pop("action/2")
        index, result = select_measurement("mixed", rows, p)
        self.assertEqual(index, 1)
        self.assertFalse(result["passed"])

    def test_failed_identity_and_unqualified_transfer_are_refused(self):
        p = protocol()
        request = {"experiment": "EXP-0006", "kind": "development", "stage": "tiny", "arm": "direct",
                   "condition": "lr003", "seed": 9103, "original": None, "source": driver.identity(), "development_transfer": False}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = root / "transitions-development-failed"
            old.mkdir()
            (old / "request.json").write_bytes(canonical_bytes(request))
            with self.assertRaisesRegex(ContractError, "already attempted"):
                driver.admit(root, p, request)
            with self.assertRaisesRegex(ContractError, "three-seed"):
                driver.require_transfer(root, p, old)
            altered = {**request, "stage": "one"}
            with self.assertRaisesRegex(ContractError, "preceding"):
                driver.admit(root, p, altered)

    def test_model_boundary_and_scalar_shape(self):
        snapshot = {"schema_version": "noetloom.transitions_parameters.v1", "arm": "shared_transition", "seed": 1, "step": 0,
                    "tensors": {"weight": [[[float(i == j) for j in range(8)] for i in range(8)] for _ in range(4)], "bias": [[0.0] * 8 for _ in range(4)]}}
        validate_snapshot(snapshot)
        first, states = scalar_forward(snapshot, [0, 1] * 4, [0, 1, 2])
        self.assertEqual(first[0], [-1, 1] * 4)
        resumed, _ = advance(snapshot, states[0], 1)
        self.assertEqual(first[1], resumed)
        with self.assertRaises(ContractError):
            advance(snapshot, states[0], 4)
        bad = copy.deepcopy(snapshot)
        bad["tensors"]["weight"][0][0][0] = float("nan")
        with self.assertRaises(ContractError):
            validate_snapshot(bad)
        self.assertEqual(parameter_count("shared_transition"), 288)
        self.assertEqual(parameter_count("direct"), 14536)
        self.assertGreater(sum(forward_ops("direct", 6).values()), sum(forward_ops("direct", 3).values()))
        for name in ("transition_model.py", "transition_torch.py"):
            tree = ast.parse((ROOT / "noetloom" / name).read_text())
            imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
            self.assertFalse(imports & {"transition_data", "transition_worker"})

    def test_every_seed_is_required_for_stage_selection(self):
        p = protocol()
        source = driver.identity()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index, seed in enumerate(p["development_seeds"]):
                directory = root / ("transitions-development-" + str(seed))
                directory.mkdir()
                (directory / "request.json").write_bytes(canonical_bytes({"experiment": "EXP-0006", "kind": "development",
                    "arm": "direct", "stage": "mixed", "condition": "lr003", "seed": seed, "source": source}))
                (directory / "manifest.json").write_text("{}")
                (directory / "fit.json").write_bytes(canonical_bytes({"acquisition": {"passed": index != 2}}))
            with patch.object(driver, "manifest", return_value={"status": "passed"}):
                self.assertIsNone(driver.stage_selection(root, p, "direct", "mixed"))
                (directory / "fit.json").write_bytes(canonical_bytes({"acquisition": {"passed": True}}))
                self.assertEqual(driver.stage_selection(root, p, "direct", "mixed"), "lr003")

    def test_irrelevant_cli_arguments_cannot_change_scientific_identity(self):
        p = protocol()
        original = {"kind": "development", "stage": "tiny", "arm": "direct", "condition": "lr003", "seed": 9103,
                    "original": None, "development_transfer": False}
        altered = {**original, "original": "/unused/path"}
        self.assertEqual(driver.attempt_key(original), driver.attempt_key(altered))
        with self.assertRaisesRegex(ContractError, "replay arguments"):
            driver.validate_request(altered, p)
        replay = {"kind": "replay", "original": "/tmp/a/../b", "development_transfer": False}
        self.assertEqual(driver.attempt_key(replay), driver.attempt_key({**replay, "original": "/tmp/b"}))
        with self.assertRaisesRegex(ContractError, "fit arguments"):
            driver.validate_request({**replay, "arm": "direct"}, p)

    def test_saved_transfer_scores_and_controls_are_recomputed(self):
        p = protocol()
        rows = generate(p, "tiny")["training"][:2]
        fresh = {"predictions": [row["targets"][-1] for row in rows], "scored": {"sentinel": "fresh"}}
        expected_controls = {"copy": "fresh"}
        state = {"state": "fresh"}
        engine = SimpleNamespace(Model=SimpleNamespace(restore=lambda _: object()))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, parent, output = root / "transfer", root / "fit", root / "verify"
            for path in (original, parent, output):
                path.mkdir()
                (path / "protocol.json").write_bytes(canonical_bytes(p))
            for name in ("manifest.json", "selected.json", "parameters-0.json"):
                (parent / name).write_text("{}")
            (original / "request.json").write_bytes(canonical_bytes({"kind": "replay", "development_transfer": True,
                "original": "/previous-cache/fit", "original_manifest_sha256": file_digest(parent / "manifest.json")}))
            (original / "manifest.json").write_text("{}")
            (original / "transfer-data.json").write_bytes(canonical_bytes({"rows": rows}))
            (original / "transfer.json").write_bytes(canonical_bytes(fresh))
            (original / "controls.json").write_bytes(canonical_bytes(expected_controls))
            (original / "transfer-state.json").write_bytes(canonical_bytes(state))
            def persist(*args, **kwargs):
                (output / "transfer-state.json").write_bytes(canonical_bytes(state))
                return {"continued_transitions": 3}
            with patch("noetloom.transition_worker.transfer", return_value=rows), \
                 patch("noetloom.transition_worker.evaluate", return_value=fresh), \
                 patch("noetloom.transition_worker.controls", return_value=expected_controls), \
                 patch("noetloom.transition_worker.persist_states", side_effect=persist), \
                 patch("noetloom.transition_worker.restart_states"), \
                 patch("noetloom.transition_worker.reference_check", return_value={}):
                request = {"original": str(original), "development_transfer": False}
                replay_transfer(engine, p, request, output, Work())
                self.assertEqual(read_json(output / "replay.json")["status"], "passed")
                (original / "transfer.json").write_bytes(canonical_bytes({**fresh, "scored": {"sentinel": "fabricated"}}))
                with self.assertRaisesRegex(ContractError, "predictions or scores"):
                    replay_transfer(engine, p, request, output, Work())
                (original / "transfer.json").write_bytes(canonical_bytes(fresh))
                (original / "controls.json").write_bytes(canonical_bytes({"copy": "fabricated"}))
                with self.assertRaisesRegex(ContractError, "control predictions or scores"):
                    replay_transfer(engine, p, request, output, Work())


if __name__ == "__main__":
    unittest.main()
