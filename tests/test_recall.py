from __future__ import annotations

import hashlib
import unittest
from unittest.mock import patch

from helpers import protocol, small_protocol
from noetloom.contracts import ContractError, canonical_bytes, query_count
from noetloom.recall import Event, MemoryControl, evaluate, make_episode


class RecallTests(unittest.TestCase):
    def test_exact_update_delete_and_unknown_semantics(self):
        control = MemoryControl("exact_memory", 1)
        self.assertIsNone(control.predict("a"))
        control.observe("write", "a", 3)
        control.observe("write", "b", 4)
        control.observe("write", "a", 9)
        self.assertEqual(control.predict("a"), 9)
        self.assertEqual(control.predict("b"), 4)
        control.observe("delete", "a", None)
        self.assertIsNone(control.predict("a"))

    def test_stale_control_really_ignores_updates_and_deletes(self):
        control = MemoryControl("stale_memory", 2)
        control.observe("write", "a", 3)
        control.observe("write", "a", 9)
        control.observe("delete", "a", None)
        self.assertEqual(control.predict("a"), 3)

    def test_bounded_control_uses_write_recency_not_read_recency(self):
        control = MemoryControl("bounded_memory", 2)
        control.observe("write", "a", 1)
        control.observe("write", "b", 2)
        self.assertEqual(control.predict("a"), 1)
        control.observe("write", "c", 3)
        self.assertIsNone(control.predict("a"))
        control.observe("write", "b", 4)
        control.observe("write", "d", 5)
        self.assertIsNone(control.predict("c"))
        self.assertEqual(control.predict("b"), 4)

    def test_observation_excludes_labels_and_phase_metadata(self):
        event = Event("query", "a", phase="revision")
        self.assertEqual(event.observation(), {"kind": "query", "key": "a", "value": None})
        observed = []
        original = MemoryControl.observe

        def record(control, kind, key, value):
            observed.append((kind, key, value))
            original(control, kind, key, value)

        with patch.object(MemoryControl, "observe", record):
            evaluate(small_protocol(), lambda _: None)
        self.assertTrue(observed)
        self.assertTrue(all(kind in {"write", "delete"} for kind, _, _ in observed))

    def test_generated_revisions_change_values_and_are_disjoint_from_deletions(self):
        value = protocol()
        events = make_episode(value, value["splits"][0], 11, 0)
        prior = {}
        revised = set()
        deleted = set()
        for event in events:
            if event.kind == "write":
                if event.key in prior:
                    self.assertNotEqual(prior[event.key], event.value)
                    revised.add(event.key)
                prior[event.key] = event.value
            elif event.kind == "delete":
                deleted.add(event.key)
        self.assertEqual(len(revised), 1)
        self.assertEqual(len(deleted), 1)
        self.assertFalse(revised & deleted)

    def test_repeatable_results_and_reference_control_signature(self):
        value = small_protocol()
        first, second = [], []
        result = evaluate(value, first.append)
        self.assertEqual(result, evaluate(value, second.append))
        self.assertEqual(first, second)
        self.assertEqual(result["predictions"], query_count(value) * 4)
        self.assertEqual(result["verdict"], "passed")
        self.assertFalse(result["learning_demonstrated"])
        for rows in result["by_split_and_phase"].values():
            for score in rows["exact_memory"].values():
                self.assertEqual(score["correct"], score["total"])
            self.assertEqual(rows["stale_memory"]["revision"]["correct"], 0)
            self.assertEqual(rows["stale_memory"]["deletion"]["correct"], 0)
            self.assertEqual(rows["no_memory"]["initial"]["correct"], 0)

    def test_input_hashes_are_from_observations_not_split_labels(self):
        value = small_protocol()
        result = evaluate(value, lambda _: None)
        split = value["splits"][0]
        events = make_episode(value, split, value["seeds"][0], 0)
        expected = hashlib.sha256(canonical_bytes([e.observation() for e in events])).hexdigest()
        self.assertEqual(result["input_digests"][split["name"]][0], expected)
        with patch("noetloom.recall.make_episode", return_value=events):
            with self.assertRaisesRegex(ContractError, "duplicate episode input"):
                evaluate(value, lambda _: None)

    def test_an_insensitive_negative_control_fails_the_harness(self):
        value = small_protocol()
        value["bounded_memory_slots"] = 256
        result = evaluate(value, lambda _: None)
        self.assertEqual(result["verdict"], "failed")
        self.assertFalse(result["checks"]["negative_controls_sensitive"])
        self.assertFalse(result["checks"]["bounded_delayed_recall_sensitive"])

    def test_positive_reference_corruption_is_detected(self):
        with patch.object(MemoryControl, "predict", return_value=None):
            result = evaluate(small_protocol(), lambda _: None)
        self.assertEqual(result["verdict"], "failed")
        self.assertFalse(result["checks"]["exact_reference"])
