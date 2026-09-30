from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from noetloom import coordinates_model, coordinates_worker, state_rep_data
from noetloom.contracts import ContractError, read_json
from noetloom.state_rep_contracts import acquisition_gate


ROOT = Path(__file__).resolve().parents[1]


def protocol():
    return read_json(ROOT / "experiments/EXP-0008/protocol.json")


def tiny_measurement(*, action_accuracy=1.0, reconstruction_accuracy=1.0):
    groups = {"all": {"cases": 10, "all_prefix_exact_accuracy": 1.0},
              "length/1": {"cases": 5, "all_prefix_exact_accuracy": 1.0}}
    groups.update({f"action/{action}": {"cases": 5,
                    "all_prefix_exact_accuracy": action_accuracy} for action in range(4)})
    return {"training": {"loss": 0.2, "scored": groups,
                         "reconstruction": {"accuracy": reconstruction_accuracy}}}


class CoordinatesWorkerTests(unittest.TestCase):
    def setUp(self):
        self.protocol = protocol()

    def test_work_counts_encoded_auxiliary_and_native_resume_arithmetic(self):
        work = coordinates_worker.Work(self.protocol)
        work.forward("reversible", [2, 3])
        work.auxiliary("reversible", 3)
        # Native-state resume performs every transition/prefix but skips the encoder.
        work.forward("reversible", [2, 1], encoded=False)
        expected = {key: 0 for key in ("multiply", "add", "tanh")}
        for length in (2, 3):
            for key, value in coordinates_model.forward_ops("reversible", length).items():
                expected[key] += value
        for key, value in coordinates_model.forward_ops("reversible", 0).items():
            expected[key] += 3 * 2 * value
        for length in (2, 1):
            resumed = coordinates_model.forward_ops("reversible", length)
            initial = coordinates_model.forward_ops("reversible", 0)
            for key in expected:
                expected[key] += resumed[key] - initial[key]
        self.assertEqual(work.counts["dense_forward_ops"], expected)
        self.assertEqual(work.counts["presentations"], 4)
        self.assertEqual(work.counts["forward_prefixes"], 8)
        self.assertEqual(work.counts["auxiliary_observations"], 3)

    def test_work_rejects_per_run_update_presentation_and_auxiliary_limits(self):
        cases = (("updates", "max_updates_per_run"),
                 ("presentations", "max_presentations_per_run"),
                 ("auxiliary_observations", "max_auxiliary_observations_per_run"))
        for counter, limit in cases:
            with self.subTest(counter=counter), self.assertRaises(ContractError):
                coordinates_worker.Work(self.protocol).add(counter, self.protocol["budget"][limit] + 1)

    def test_audit_stays_in_training_and_validation_and_never_renders_other_splits(self):
        with patch.object(state_rep_data, "development", side_effect=AssertionError("development called")), \
             patch.object(state_rep_data, "continuations", side_effect=AssertionError("continuations called")), \
             patch.object(state_rep_data, "transfer_words", side_effect=AssertionError("transfer words called")):
            result = coordinates_worker.audit(self.protocol)
        self.assertFalse(result["development_or_final_trajectories_rendered"])
        dataset = state_rep_data.generate(self.protocol, "nonlinear", "mixed")
        training = set(state_rep_data.partition(self.protocol["data"])["training"])
        raw = state_rep_data.acquisition_raw(self.protocol, "mixed")["training"]
        self.assertEqual(len(raw), len(dataset["training"]))
        for (initial, word, _), row in zip(raw, dataset["training"]):
            self.assertEqual(row["initial"], state_rep_data.observe(self.protocol["data"], initial, "nonlinear"))
            self.assertTrue(set(state_rep_data.path(self.protocol["data"], initial, word)) <= training)

    def test_tiny_gate_positive_and_action_or_reconstruction_failures_are_diagnostic_only(self):
        before = state_rep_data.generate(self.protocol, "nonlinear", "tiny")
        self.assertTrue(acquisition_gate(self.protocol, "tiny", tiny_measurement())["passed"])
        action_failure = tiny_measurement(action_accuracy=0.99)
        self.assertFalse(acquisition_gate(self.protocol, "tiny", action_failure)["passed"])
        reconstruction_failure = tiny_measurement(reconstruction_accuracy=0.98)
        self.assertFalse(acquisition_gate(self.protocol, "tiny", reconstruction_failure)["passed"])
        self.assertEqual(state_rep_data.generate(self.protocol, "nonlinear", "tiny"), before)

    def test_verify_fit_rejects_incomplete_curve_and_changed_data_before_restore(self):
        class Model:
            restore_calls = 0

            @classmethod
            def restore(cls, _snapshot):
                cls.restore_calls += 1
                raise AssertionError("model restore must not happen before integrity checks")

        Engine = SimpleNamespace(Model=Model)

        stage = "tiny"
        expected_data = state_rep_data.generate(self.protocol, "nonlinear", stage)
        expected_steps = self.protocol["training"]["measurement_steps"][stage]
        with tempfile.TemporaryDirectory() as root:
            parent = Path(root) / "parent"
            destination = Path(root) / "destination"
            parent.mkdir()
            destination.mkdir()
            fit_identity = {"stage": stage, "arm": "latent", "condition": "lr003", "seed": 12003}
            (parent / "fit.json").write_text(json.dumps({**fit_identity,
                "measurements": [{"step": step} for step in expected_steps[:-1]]}))
            (parent / "request.json").write_text(json.dumps({"stage": stage, "arm": "latent",
                                                               "condition": "lr003", "seed": 12003}))
            (parent / "data.json").write_text(json.dumps(expected_data))
            Model.restore_calls = 0
            with self.assertRaises(ContractError):
                coordinates_worker.verify_fit(Engine, self.protocol, parent, destination,
                                              coordinates_worker.Work(self.protocol))
            self.assertEqual(Model.restore_calls, 0)

            (parent / "fit.json").write_text(json.dumps({**fit_identity,
                "measurements": [{"step": step} for step in expected_steps]}))
            altered = copy.deepcopy(expected_data)
            altered["training"][0]["targets"][0][0] += 0.5
            (parent / "data.json").write_text(json.dumps(altered))
            with self.assertRaises(ContractError):
                coordinates_worker.verify_fit(Engine, self.protocol, parent, destination,
                                              coordinates_worker.Work(self.protocol))
            self.assertEqual(Model.restore_calls, 0)


if __name__ == "__main__":
    unittest.main()
