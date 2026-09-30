from __future__ import annotations

import json
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from noetloom.storage import StorageError
from scripts import rust


class RustDriverTests(unittest.TestCase):
    def test_build_sampling_is_live_and_post_exit_admission_remains_strict(self):
        for final_failure in (False, True):
            with self.subTest(final_failure=final_failure):
                process = SimpleNamespace(wait=Mock(side_effect=[subprocess.TimeoutExpired('cargo', 1), 0]),
                                          poll=Mock(return_value=0))
                observed = []

                def inspect(tooling, min_free, *, live=False):
                    observed.append(live)
                    if not live and final_failure:
                        raise StorageError('strict post-build inventory failed')
                    return {}

                with patch.object(rust.subprocess, 'Popen', return_value=process), \
                        patch.object(rust, 'check_tooling', side_effect=inspect):
                    if final_failure:
                        with self.assertRaisesRegex(StorageError, 'post-build'):
                            rust.cargo(['check'], {}, Path('/fixture'), {'min_free_disk_bytes': 1})
                    else:
                        rust.cargo(['check'], {}, Path('/fixture'), {'min_free_disk_bytes': 1})
                self.assertEqual(observed, [True, False])

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
