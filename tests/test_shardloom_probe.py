from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from noetloom.storage import StorageError
from scripts.shardloom_probe import checked_rows, field_map, fixture_rows, native_evidence, queries


class ShardLoomProbeTests(unittest.TestCase):
    def test_reference_queries_cover_count_filter_and_grouping(self):
        rows = fixture_rows()
        cases = queries(Path("/fixture/traces.csv"), rows)
        self.assertEqual(cases[0][2], [{"n": 512}])
        self.assertEqual(cases[1][2], [{"n": 128}])
        self.assertEqual(sum(row["n"] for row in cases[2][2]), 512)
        self.assertEqual(sum(row["scalar_work"] for row in cases[2][2]), 1152)

    def test_route_or_fallback_markers_alone_do_not_prove_execution(self):
        fields = {"fallback_attempted": "false", "external_engine_invoked": "false",
                  "runtime_execution": "true", "upstream_vortex_scan_called": "true",
                  "public_workflow_route_attached": "true", "public_workflow_route_status": "admitted",
                  "public_workflow_execution_mode": "native_vortex",
                  "public_workflow_local_source_execution_mode": "prepared_vortex_then_native_vortex",
                  "native_vortex_result_export_all_targets_committed": "true"}
        envelope = {"schema_version": "shardloom.output.v2"}
        self.assertTrue(native_evidence(envelope, fields))
        for key in fields:
            changed = fields.copy()
            changed.pop(key)
            self.assertFalse(native_evidence(envelope, changed), key)
        self.assertFalse(native_evidence(envelope, {**fields, "external_engine_invoked": "true"}))
        with self.assertRaisesRegex(StorageError, "duplicate"):
            field_map({"fields": [{"key": "fallback_attempted", "value": "false"},
                                   {"key": "fallback_attempted", "value": "true"}]})

    def test_query_rows_refuse_boolean_counts_and_unbounded_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            path.write_text('{"n":512}\n')
            self.assertEqual(checked_rows(path), [{"n": 512}])
            for text in ('{"n":true}\n', '[]\n', 'x' * 65537):
                path.write_text(text)
                with self.assertRaises(StorageError):
                    checked_rows(path)
