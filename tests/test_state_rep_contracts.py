from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from noetloom.contracts import ContractError, load_policy
from noetloom.state_rep_contracts import acquisition_gate, select_measurement, validate_protocol


ROOT = Path(__file__).resolve().parents[1]


def protocol() -> dict:
    return json.loads((ROOT / "experiments/EXP-0007/protocol.json").read_text())


def measured(*, train_loss: float = 0.2, validation_loss: float = 0.2) -> dict:
    groups = {"all": {"cases": 10, "all_prefix_exact_accuracy": 1.0}}
    groups.update({f"length/{length}": {"cases": 5, "all_prefix_exact_accuracy": 1.0}
                   for length in (1, 2, 3)})
    groups.update({f"action/{action}": {"cases": 5, "all_prefix_exact_accuracy": 1.0}
                   for action in range(4)})
    return {
        "training": {"loss": train_loss, "scored": copy.deepcopy(groups),
                     "reconstruction": {"accuracy": 1.0}},
        "validation": {"loss": validation_loss, "scored": copy.deepcopy(groups),
                       "reconstruction": {"accuracy": 1.0}},
    }


class StateRepresentationContractTests(unittest.TestCase):
    def test_actual_protocol_and_policy_validate(self):
        validate_protocol(protocol(), load_policy(ROOT, "local-calibration"))

    def test_identity_resource_and_data_boundary_mutations_are_rejected(self):
        original = protocol()
        mutations = []

        changed = copy.deepcopy(original)
        changed["final_access"] = True
        mutations.append(changed)

        changed = copy.deepcopy(original)
        changed["conditions"][0]["rate"] = 0.004
        mutations.append(changed)

        changed = copy.deepcopy(original)
        changed["budget"]["max_attempts"] += 1
        mutations.append(changed)

        changed = copy.deepcopy(original)
        changed["data"]["world_seed"] += 1
        mutations.append(changed)

        for mutated in mutations:
            with self.subTest(mutated=mutated["id"]):
                with self.assertRaises(ContractError):
                    validate_protocol(mutated, load_policy(ROOT, "local-calibration"))

    def test_every_complete_rollout_slice_and_reconstruction_gate_is_independent(self):
        p = protocol()
        base = measured()
        self.assertTrue(acquisition_gate(p, "mixed", base)["passed"])

        slices = ["all", *(f"length/{n}" for n in (1, 2, 3)),
                  *(f"action/{n}" for n in range(4))]
        for split in ("training", "validation"):
            for name in slices:
                with self.subTest(split=split, gate=name):
                    candidate = copy.deepcopy(base)
                    floor = (p["acquisition"][split + "_all_prefix_accuracy"] if name == "all"
                             else p["acquisition"]["minimum_action_and_length_accuracy"])
                    candidate[split]["scored"][name]["all_prefix_exact_accuracy"] = floor - 0.001
                    result = acquisition_gate(p, "mixed", candidate)
                    self.assertFalse(result["passed"])
                    self.assertFalse(result["checks"][split + "/" + name])

            with self.subTest(split=split, gate="reconstruction"):
                candidate = copy.deepcopy(base)
                floor = p["acquisition"][split + "_reconstruction_accuracy"]
                candidate[split]["reconstruction"]["accuracy"] = floor - 0.001
                result = acquisition_gate(p, "mixed", candidate)
                self.assertFalse(result["passed"])
                self.assertFalse(result["checks"][split + "/reconstruction"])

    def test_nonfinite_metrics_and_invalid_support_are_rejected(self):
        p = protocol()
        bad_inputs = []

        bad = measured()
        bad["training"]["loss"] = float("nan")
        bad_inputs.append(bad)

        bad = measured()
        bad["validation"]["scored"]["action/0"]["all_prefix_exact_accuracy"] = float("nan")
        bad_inputs.append(bad)

        bad = measured()
        bad["validation"]["reconstruction"]["accuracy"] = float("nan")
        bad_inputs.append(bad)

        bad = measured()
        bad["training"]["scored"]["length/2"]["cases"] = 0
        bad_inputs.append(bad)

        bad = measured()
        bad["training"]["scored"]["all"]["cases"] = True
        bad_inputs.append(bad)

        for invalid in bad_inputs:
            with self.assertRaises(ContractError):
                acquisition_gate(p, "mixed", invalid)

    def test_selection_uses_passing_minimum_loss_then_earliest_step(self):
        p = protocol()
        measurements = [
            {"step": 10, **measured(validation_loss=0.2)},
            {"step": 20, **measured(validation_loss=0.1)},
            {"step": 5, **measured(validation_loss=0.1)},
        ]

        index, gate = select_measurement(p, "mixed", measurements)

        self.assertEqual(index, 2)
        self.assertTrue(gate["passed"])

    def test_when_no_measurement_passes_selection_retains_minimum_loss(self):
        p = protocol()
        measurements = [
            {"step": 10, **measured(validation_loss=0.2)},
            {"step": 20, **measured(validation_loss=0.1)},
        ]
        measurements[0]["validation"]["scored"]["length/2"]["all_prefix_exact_accuracy"] = 0.0
        measurements[1]["validation"]["scored"]["length/2"]["all_prefix_exact_accuracy"] = 0.0

        index, gate = select_measurement(p, "mixed", measurements)

        self.assertEqual(index, 1)
        self.assertFalse(gate["passed"])
        self.assertFalse(gate["checks"]["validation/length/2"])


if __name__ == "__main__":
    unittest.main()
