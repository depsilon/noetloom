from __future__ import annotations

from copy import deepcopy
import sys
import unittest

from helpers import ROOT
from noetloom.calibration_data import SURFACES, render
from noetloom.calibration_model import scalar_forward, shapes
from noetloom.contracts import ContractError
from noetloom.input_audit import audit_inputs, require_informative_inputs

sys.path.insert(0, str(ROOT / "scripts"))
from audit_calibration_inputs import audit, consumed_rows, full_field, require_transfer_admission


class InputAuditTests(unittest.TestCase):
    def test_counterexample_reaches_identical_outputs_in_actual_scalar_model_path(self):
        snapshot = {"schema_version": "noetloom.calibration_parameters.v1", "role": "inference_parameters_only",
                    "arm": "shared_rows", "seed": 1, "step": 0}
        for group, layers in shapes("shared_rows").items():
            snapshot[group] = [{"weights": [(index % 7 - 3) / 20 for index in range(inputs * outputs)],
                                "bias": [index / 100 for index in range(outputs)]}
                               for inputs, outputs, _ in layers]
        for surface in SURFACES:
            inputs = [render(tuple(range(6)), query, surface, "transpose") for query in ((0, 5), (5, 0))]
            self.assertNotEqual(inputs[0], inputs[1])
            self.assertEqual(scalar_forward(snapshot, inputs[0]), scalar_forward(snapshot, inputs[1]))

    def test_opposite_answers_with_identical_consumed_inputs_are_rejected(self):
        for surface in SURFACES:
            cases = [{"values": render(tuple(range(6)), query, surface, "transpose"), "expected": answer}
                     for query, answer in (((0, 5), 1), ((5, 0), 0))]
            self.assertEqual(cases[0]["values"][:48], cases[1]["values"][:48])
            with self.assertRaisesRegex(ContractError, "different targets"):
                require_informative_inputs(audit_inputs({"probe": cases}, consumed_rows))
            # Full access distinguishes this counterexample; it does not prove learning.
            require_informative_inputs(audit_inputs({"probe": cases}, full_field))

    def test_symmetry_overlap_is_detected_even_when_raw_observations_differ(self):
        first = {"values": render(tuple(range(6)), (0, 5), "ranks"), "expected": 1}
        permuted = {"values": render(tuple(range(6)), (0, 5), "ranks", "row_permutation"), "expected": 1}
        groups = {"training": [first], "validation": [permuted, deepcopy(permuted)]}
        require_informative_inputs(audit_inputs(groups, full_field), disjoint_pairs=("training/validation",))
        result = audit_inputs(groups, consumed_rows)
        self.assertEqual(result["overlap"]["training/validation"], {"distinct_signatures": 1, "left_cases": 1, "right_cases": 2})
        require_informative_inputs(result)  # Disclosed optimization calibration permits overlap.
        with self.assertRaisesRegex(ContractError, "held-out"):
            require_informative_inputs(result, disjoint_pairs=("training/validation",))

    def test_conflicts_across_groups_and_missing_holdout_checks_are_not_silent(self):
        groups = {"training": [{"values": [1], "expected": 0}],
                  "validation": [{"values": [1], "expected": 1}]}
        result = audit_inputs(groups, full_field)
        self.assertEqual(result["conflicting_signatures"], 1)
        self.assertEqual(result["groups"]["validation"]["conflicting_cases"], 1)
        with self.assertRaisesRegex(ContractError, "different targets"):
            require_informative_inputs(result)
        safe = audit_inputs({"training": groups["training"]}, full_field)
        with self.assertRaisesRegex(ContractError, "omits required"):
            require_informative_inputs(safe, disjoint_pairs=("training/validation",))
        with self.assertRaisesRegex(ContractError, "nonempty"):
            audit_inputs({"empty": []}, full_field)

    def test_registered_partition_audit_keeps_formats_and_missing_seed_separate(self):
        result = audit()
        for surface, count in (("ranks", 30), ("sequence", 30), ("relations", 384)):
            rows = result["partition_audit"][surface]
            self.assertEqual(rows["shared_rows"]["groups"]["training"]["distinct_signatures"], count)
            for split, size in (("validation", 96), ("confirmation", 192)):
                pair = "training/" + split
                self.assertEqual(rows["shared_rows"]["overlap"][pair]["right_cases"], 0 if surface == "relations" else size)
                self.assertEqual(rows["exact_observation"]["overlap"][pair]["right_cases"], 0)
                self.assertEqual(rows["latent_orbit"]["overlap"][pair]["right_cases"], 0)
        failed = [row for row in result["historical_scores_by_format"] if not row["acquired"]]
        self.assertEqual([row["seed"] for row in failed], [8209])
        self.assertIsNone(failed[0]["canonical"])
        self.assertIsNone(failed[0]["row_permutation"])
        with self.assertRaises(ContractError):
            require_transfer_admission(result)
