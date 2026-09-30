from __future__ import annotations

import collections
import random
import unittest

from helpers import ROOT
from noetloom.contracts import ContractError, read_json
from noetloom.representation_data import (
    FAMILIES, HELDOUT, SEEN, SURFACES, decode, generate, observations, render, score,
    validate_observations,
)


def latent_key(case: dict) -> tuple:
    return tuple(case["latent_order"]), tuple(case["latent_query"])


class RepresentationDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = read_json(ROOT / "experiments/EXP-0004/protocol.json")
        cls.data = generate(cls.protocol)

    def test_known_order_queries_and_all_surface_dihedral_transforms_decode(self):
        order, query = (3, 0, 4, 1, 2), (0, 2)
        self.assertEqual(int(order.index(query[0]) < order.index(query[1])), 1)
        self.assertEqual(int(order.index(query[1]) < order.index(query[0])), 0)
        for surface in SURFACES:
            for turns in range(4):
                for reflected in (False, True):
                    values = render(order, query, surface, turns, reflected, random.Random(17))
                    with self.subTest(surface=surface, turns=turns, reflected=reflected):
                        self.assertEqual(decode(values), 1)
                        reverse = render(order, query[::-1], surface, turns, reflected, random.Random(17))
                        self.assertEqual(decode(reverse), 0)

    def test_registered_partition_sizes_latent_and_rendered_isolation(self):
        datasets = self.data
        self.assertEqual(len(datasets["training"]), 768)
        self.assertEqual(len(datasets["validation"]), 96)
        self.assertEqual(len(datasets["development"]), 32)
        self.assertEqual(len(datasets["test"]), 384)
        self.assertEqual(len(datasets["diagnostic"]), 288)
        self.assertEqual(datasets["integrity"]["latent_problems"], 1376)
        self.assertEqual(datasets["integrity"]["unique_observations"], 1568)

        ordinary = [*datasets["training"], *datasets["validation"], *datasets["development"], *datasets["test"]]
        ordinary_keys = [latent_key(case) for case in ordinary]
        self.assertEqual(len(set(ordinary_keys)), len(ordinary_keys))
        diagnostic_keys = [latent_key(case) for case in datasets["diagnostic"]]
        self.assertEqual(len(set(diagnostic_keys)), 96)
        self.assertTrue(set(diagnostic_keys).isdisjoint(ordinary_keys))
        for key in set(diagnostic_keys):
            matching = [case for case in datasets["diagnostic"] if latent_key(case) == key]
            self.assertEqual(len(matching), 3)
            self.assertEqual({case["surface"] for case in matching}, set(SURFACES))

        fields = [case["input_sha256"] for case in [*ordinary, *datasets["diagnostic"]]]
        self.assertEqual(len(set(fields)), 1568)
        self.assertEqual(len(fields), 1568)

    def test_labels_are_balanced_and_test_families_have_surface_coverage(self):
        datasets = self.data
        for name in ("training", "validation", "development"):
            labels = collections.Counter(case["expected"] for case in datasets[name])
            self.assertEqual(labels, {0: len(datasets[name]) // 2, 1: len(datasets[name]) // 2})
        for family in FAMILIES:
            rows = [case for case in datasets["test"] if case["family"] == family]
            self.assertEqual(len(rows), 96)
            labels = collections.Counter(case["expected"] for case in rows)
            self.assertEqual(labels, {0: 48, 1: 48})
            self.assertEqual(collections.Counter(case["surface"] for case in rows),
                             {surface: 32 for surface in SURFACES})

    def test_seen_heldout_reflection_and_diagnostic_rotation_contracts(self):
        data = self.data
        for name in ("training", "validation", "development"):
            for case in data[name]:
                self.assertIn(case["rotation"], SEEN[case["surface"]])
                self.assertFalse(case["reflected"])
        for family in FAMILIES:
            for case in (row for row in data["test"] if row["family"] == family):
                if family in {"base", "reflection"}:
                    self.assertIn(case["rotation"], SEEN[case["surface"]])
                else:
                    self.assertEqual(case["rotation"], HELDOUT[case["surface"]])
                self.assertEqual(case["reflected"], family in {"reflection", "joint"})
        for case in data["diagnostic"]:
            self.assertEqual(case["rotation"], HELDOUT[case["surface"]])
            self.assertFalse(case["reflected"])

    def test_observation_boundary_strips_metadata_and_rejects_invalid_inputs(self):
        cases = self.data["test"][:2]
        runtime = observations(cases)
        validate_observations(runtime)
        self.assertEqual(set(runtime), {"schema_version", "samples"})
        self.assertTrue(all(set(sample) == {"values"} for sample in runtime["samples"]))
        for hidden in ("expected", "family", "surface", "latent_order", "latent_query", "rotation", "reflected"):
            self.assertTrue(all(hidden not in sample for sample in runtime["samples"]))

        invalid = [
            {"schema_version": runtime["schema_version"], "samples": [{"values": [0.0] * 64, "expected": 1}]},
            {"schema_version": runtime["schema_version"], "samples": [{"values": [0.0] * 63}]},
            {"schema_version": runtime["schema_version"], "samples": [{"values": [2.1] + [0.0] * 63}]},
            {"schema_version": runtime["schema_version"], "samples": [{"values": [float("nan")] + [0.0] * 63}]},
            {"schema_version": runtime["schema_version"], "samples": [{"values": [True] + [0.0] * 63}]},
            {"schema_version": runtime["schema_version"], "samples": []},
            {"schema_version": runtime["schema_version"], "samples": [{"values": [0.0] * 64} for _ in range(513)]},
        ]
        for value in invalid:
            with self.subTest(size=len(value["samples"])):
                with self.assertRaises(ContractError):
                    validate_observations(value)

    def test_decode_rejects_bad_anchors_marks_grammar_and_nontransitive_relations(self):
        base = render((0, 1, 2, 3, 4), (0, 1), "ranks", 0, False, random.Random(7))
        missing_anchor = list(base)
        missing_anchor[63] = 0.0
        with self.assertRaises(ContractError):
            decode(missing_anchor)

        # Construct two coordinate frames with the same fiducial pattern. The decoder
        # must reject multiple orientation matches before trying to interpret grammar.
        ambiguous = [0.0] * 64
        index_grid = [list(range(row * 8, (row + 1) * 8)) for row in range(8)]
        targets = ((63, 2.0), (62, 1.5), (55, -1.5))
        for turns in (0, 1):
            mapped = [value for row in transform_for_test(index_grid, turns) for value in row]
            for destination, marker in targets:
                ambiguous[mapped[destination]] = marker
        with self.assertRaisesRegex(ContractError, "ambiguous"):
            decode(ambiguous)

        bad_marks = list(base)
        bad_marks[5 * 8 + 1] = 1.0
        with self.assertRaisesRegex(ContractError, "query marks"):
            decode(bad_marks)

        relation = render((0, 1, 2, 3, 4), (0, 1), "relations", 0, False, random.Random(7))
        for left, right, value in ((0, 1, 1.0), (1, 2, 1.0), (2, 0, 1.0)):
            relation[left * 8 + right] = value
            relation[right * 8 + left] = -value
        with self.assertRaisesRegex(ContractError, "total order"):
            decode(relation)

        outside = list(base)
        outside[6 * 8] = 0.5
        with self.assertRaisesRegex(ContractError, "outside grammar"):
            decode(outside)

    def test_score_rejects_wrong_count_classes_and_corrupt_reference(self):
        case = {"values": render((3, 0, 4, 1, 2), (0, 2), "sequence", 2, True, random.Random(22)),
                "expected": 1, "family": "base"}
        self.assertEqual(score([case], [1])["base"]["accuracy"], 1.0)
        with self.assertRaises(ContractError):
            score([case], [])
        for prediction in (True, 2, -1):
            with self.subTest(prediction=prediction), self.assertRaises(ContractError):
                score([case], [prediction])
        corrupt = dict(case, expected=0)
        with self.assertRaisesRegex(ContractError, "reference disagrees"):
            score([corrupt], [0])


def transform_for_test(grid: list[list[int]], turns: int) -> list[list[int]]:
    """Index-grid rotation matching the generator's clockwise quarter turns."""
    result = [row[:] for row in grid]
    for _ in range(turns):
        result = [list(row) for row in zip(*result[::-1])]
    return result


if __name__ == "__main__":
    unittest.main()
