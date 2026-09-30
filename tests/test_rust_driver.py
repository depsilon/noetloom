from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noetloom.storage import StorageError
from scripts import rust


class RustDriverTests(unittest.TestCase):
    def test_stale_compiled_source_identity_is_refused(self):
        process = subprocess.CompletedProcess([], 0, json.dumps({"build": {"source_sha256": "old"}}).encode(), b"")
        with patch.object(rust.subprocess, "run", return_value=process):
            with self.assertRaisesRegex(StorageError, "compiled Rust identity"):
                rust.fixture_output(Path("/fixture/binary"), "run", Path("/fixture/state"),
                                    {"source_sha256": "current"})

    def test_final_storage_failure_cannot_leave_a_passed_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            cache.mkdir()
            tooling = root / "tooling"
            binary = tooling / "cargo-target/debug/examples/foundation"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"disposable executable identity fixture")
            value = {"kind": "dense", "data": [3.0]}
            outputs = [{"execution": {"commit": {"after": "snapshot"}, "metrics": {}}, "emitted_value": value},
                       {"snapshot": "snapshot", "value": value}]
            with patch.object(rust, "cargo"), patch.object(rust, "fixture_output", side_effect=outputs), \
                    patch.object(rust, "rust_source", return_value={"source_sha256": "current", "source_files": []}), \
                    patch.object(rust, "check_tooling", return_value={}), \
                    patch.object(rust, "storage_snapshot", side_effect=StorageError("final admission refused")):
                with self.assertRaisesRegex(StorageError, "final admission refused"):
                    rust.run_fixture(cache, tooling, {}, {"min_free_disk_bytes": 1})
            run = next(cache.iterdir())
            self.assertFalse((run / "manifest.json").exists())
            self.assertEqual(json.loads((run / "failure.json").read_text())["status"], "failed")
