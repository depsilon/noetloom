"""EXP-0010 view adapters and float32 input audit, using registered non-final data."""
from __future__ import annotations

import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from noetloom import representation_bridge_data as bridge
from noetloom.contracts import ContractError
from noetloom.input_audit import audit_inputs
from noetloom import state_rep_data as source

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((ROOT / "experiments/EXP-0010/protocol.json").read_text())

try:
    from noetloom import coordinates_torch as engine
except ImportError:
    engine = None


class Work:
    def __init__(self):
        self.counts = {}

    def add(self, key, amount):
        self.counts[key] = self.counts.get(key, 0) + amount


class RepresentationBridgeDataTests(unittest.TestCase):
    def test_transform_equations_inverse_and_orthogonal_geometry(self):
        vector = [((index * 7) % 13 - 6) / 5 for index in range(10)]
        change = PROTOCOL["observation_change"]
        shift = bridge.transform(PROTOCOL, "shift", vector)
        self.assertEqual(shift, [value + bias for value, bias in zip(vector, change["shift"])])
        self.assertTrue(all(math.isclose(recovered, original, abs_tol=2e-14)
                            for recovered, original in zip(
                                [value - bias for value, bias in zip(shift, change["shift"])], vector)))

        remix = bridge.transform(PROTOCOL, "remix", vector)
        centered = [value - bias for value, bias in zip(remix, change["shift"])]
        recovered = [sum(change["remix_matrix"][row][column] * centered[row] for row in range(10))
                     for column in range(10)]
        self.assertTrue(all(math.isclose(left, right, abs_tol=2e-14)
                            for left, right in zip(recovered, vector)))
        other = [value + (0.1 if index % 2 else -0.2) for index, value in enumerate(vector)]
        old_distance = math.sqrt(sum((left - right) ** 2 for left, right in zip(vector, other)))
        new_distance = math.sqrt(sum((left - right) ** 2 for left, right in zip(
            bridge.transform(PROTOCOL, "remix", vector), bridge.transform(PROTOCOL, "remix", other))))
        self.assertAlmostEqual(old_distance, new_distance, places=13)
        geometry = bridge._geometry(PROTOCOL)
        self.assertGreater(geometry["offset_l2"], 0)
        self.assertLess(geometry["max_orthogonality_error"], 1e-12)

    def test_vector_generation_charges_only_new_views_and_preserves_row_contract(self):
        work = Work()
        old = bridge.transform(PROTOCOL, "old", [0.25] * 10, work)
        shifted = bridge.transform(PROTOCOL, "shift", old, work)
        remixed = bridge.transform(PROTOCOL, "remix", old, work)
        self.assertEqual(old, [0.25] * 10)
        self.assertEqual(work.counts, {"view_vectors": 2, "view_add": 110, "view_multiply": 100})

        data = bridge.generate(PROTOCOL, "shift", "one")
        raw = source.generate(PROTOCOL, "nonlinear", "one")
        self.assertEqual(set(data), {"training", "validation"})
        self.assertEqual(set(data["training"][0]), {"initial", "actions", "targets", "family"})
        for split in data:
            self.assertEqual(len(data[split]), len(raw[split]))
            for actual, original in zip(data[split][:8], raw[split][:8]):
                self.assertEqual(actual["initial"], bridge.transform(PROTOCOL, "shift", original["initial"]))
                self.assertEqual(actual["targets"], [bridge.transform(PROTOCOL, "shift", v)
                                                       for v in original["targets"]])
                self.assertEqual(actual["actions"], original["actions"])
                self.assertEqual(actual["family"], original["family"])
                self.assertEqual(set(actual), {"initial", "actions", "targets", "family"})
        self.assertEqual(len(shifted), len(remixed))

    def test_development_and_continuation_vectors_are_transformed_at_every_boundary(self):
        raw_dev = source.development(PROTOCOL, "nonlinear")
        new_dev = bridge.development(PROTOCOL, "remix")
        self.assertEqual(len(raw_dev), len(new_dev))
        for old, new in zip(raw_dev[:10], new_dev[:10]):
            self.assertEqual(new["initial"], bridge.transform(PROTOCOL, "remix", old["initial"]))
            self.assertEqual(new["targets"], [bridge.transform(PROTOCOL, "remix", value)
                                                for value in old["targets"]])
            self.assertEqual((new["actions"], new["family"]), (old["actions"], old["family"]))
            self.assertEqual(set(new), {"initial", "actions", "targets", "family"})

        raw_pairs = source.continuations(PROTOCOL, "nonlinear")
        pairs = bridge.continuations(PROTOCOL, "remix")
        self.assertEqual(len(raw_pairs), len(pairs))
        for old, new in zip(raw_pairs[:8], pairs[:8]):
            for history in ("history_a", "history_b"):
                self.assertEqual(new[history]["initial"], bridge.transform(
                    PROTOCOL, "remix", old[history]["initial"]))
                self.assertEqual(new[history]["targets"], [bridge.transform(PROTOCOL, "remix", value)
                                                            for value in old[history]["targets"]])
                self.assertEqual((new[history]["actions"], new[history]["family"]),
                                 (old[history]["actions"], old[history]["family"]))
            self.assertEqual(new["current"], bridge.transform(PROTOCOL, "remix", old["current"]))
            self.assertEqual(new["targets"], [bridge.transform(PROTOCOL, "remix", value)
                                               for value in old["targets"]])
            self.assertEqual((new["suffix"], new["family"]), (old["suffix"], old["family"]))
            self.assertEqual(set(new), {"history_a", "history_b", "current", "suffix", "targets", "family"})

    def test_signature_exposes_float32_opposing_target_collision(self):
        first = {"initial": [1.0] * 10, "actions": [2]}
        second = {"initial": [1.0 + 1e-8] * 10, "actions": [2]}
        self.assertEqual(bridge.signature(first), bridge.signature(second))
        colliding = [
            {"initial": first["initial"], "actions": [2], "expected": [0.0] * 10},
            {"initial": second["initial"], "actions": [2], "expected": [1.0] * 10},
        ]
        self.assertEqual(audit_inputs({"synthetic": colliding}, bridge.signature)["conflicting_signatures"], 1)

    def test_unknown_view_malformed_vectors_and_float32_overflow_are_rejected(self):
        for view in ("nonlinear", "final", "", None):
            with self.subTest(view=view), self.assertRaises(ContractError):
                bridge.transform(PROTOCOL, view, [0.0] * 10)
        for vector in ([0.0] * 9, [0.0] * 9 + [float("nan")], [0.0] * 9 + [1e100]):
            with self.subTest(vector=vector[-1]), self.assertRaises(ContractError):
                bridge.signature({"initial": vector, "actions": [0]})
        with patch.object(source, "generate") as generate:
            with self.assertRaises(ContractError):
                bridge.generate(PROTOCOL, "canonical", "one")
            generate.assert_not_called()

    def test_audit_checks_actual_float32_partitions_injectivity_and_old_new_overlap(self):
        report = bridge.audit(PROTOCOL)
        self.assertIn("old_partition_audit", report)
        self.assertLess(report["transform_geometry"]["max_orthogonality_error"], 1e-12)
        self.assertGreater(report["transform_geometry"]["offset_l2"], 0)
        self.assertEqual(set(report["views"]), {"old", "shift", "remix"})
        for name, view in report["views"].items():
            self.assertTrue(view["admitted_state_injectivity"]["injective"], name)
            overlaps = view["prefix_input_audit"]["overlap"]
            self.assertEqual(overlaps["training/validation"]["distinct_signatures"], 0, name)
            self.assertEqual(overlaps["training/development"]["distinct_signatures"], 0, name)
            self.assertEqual(overlaps["validation/development"]["distinct_signatures"], 0, name)
            self.assertEqual(view["prefix_input_audit"]["conflicting_signatures"], 0, name)
        for view in ("shift", "remix"):
            overlap = report["views"][view]["old_new_training_signature_overlap"]
            self.assertEqual(set(overlap), {"distinct_signatures", "old_cases", "new_cases"})
            self.assertGreaterEqual(overlap["distinct_signatures"], 0)
        self.assertIn("no final observations rendered", report["scope"])


@unittest.skipIf(engine is None, "optional PyTorch backend is unavailable")
class RepresentationBridgeCapacityTests(unittest.TestCase):
    def test_synthetic_translation_reparameterization_preserves_decode_and_operations(self):
        torch = engine.torch
        torch.set_num_threads(1)
        random_state = torch.random.get_rng_state()
        self.addCleanup(torch.random.set_rng_state, random_state)
        model = engine.Model("reversible", 887)
        generator = torch.Generator(device="cpu").manual_seed(991)
        with torch.no_grad():
            for name, parameter in model.named_parameters():
                if name.startswith("coupling_"):
                    parameter.copy_(torch.empty_like(parameter).uniform_(-0.045, 0.045, generator=generator))
            shift = torch.linspace(-0.35, 0.42, 10, dtype=torch.float32)
            old_transition_weight = model.transition_weight.clone()
            old_transition_bias = model.transition_bias.clone()
            translated = engine.Model.restore(model.snapshot(0))
            even = torch.tensor([0, 2, 4, 6, 8])
            odd = torch.tensor([1, 3, 5, 7, 9])
            translated.coupling_first_bias[0].sub_(model.coupling_first_weight[0] @ shift[even])
            translated.coupling_last_bias[0].sub_(shift[odd])
            translated.coupling_last_bias[1].sub_(shift[even])

        observations = torch.tensor([
            [((row * 11 + column * 3) % 17 - 8) / 9 for column in range(10)]
            for row in range(7)
        ], dtype=torch.float32)
        with torch.no_grad():
            old_encoded = model.encode(observations)
            new_encoded = translated.encode(observations + shift)
            self.assertTrue(torch.allclose(new_encoded, old_encoded, atol=3e-7, rtol=0))
            self.assertTrue(torch.allclose(translated.decode(new_encoded), observations + shift,
                                           atol=3e-7, rtol=0))
            self.assertTrue(torch.allclose(translated.decode(old_encoded), model.decode(old_encoded) + shift,
                                           atol=3e-7, rtol=0))
            self.assertTrue(torch.equal(translated.transition_weight, old_transition_weight))
            self.assertTrue(torch.equal(translated.transition_bias, old_transition_bias))


if __name__ == "__main__":
    unittest.main()
