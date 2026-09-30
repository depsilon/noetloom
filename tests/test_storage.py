from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from helpers import policy
from noetloom.storage import RunLease, RunWriter, StorageError, storage_snapshot, tree_bytes, validate_cache


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="noetloom-storage-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        self.repo = self.home / "Documents/repo"
        self.repo.mkdir(parents=True)
        self.cache = self.home / ".cache/noetloom"
        self.policy = policy()
        self.policy.update(min_free_disk_bytes=1, max_workspace_bytes=1024 * 1024)

    def test_refuses_checkout_ancestors_and_known_mac_sync_roots(self):
        candidates = [self.repo, self.repo / "runs", self.repo.parent, self.home, Path("/"),
                      self.home / "Desktop/runs", self.home / "documents/runs",
                      self.home / "Library/CloudStorage/provider/runs",
                      self.home / "Library/Mobile Documents/runs"]
        for path in candidates:
            with self.subTest(path=path):
                with self.assertRaises(StorageError):
                    validate_cache(path, self.repo, home=self.home, platform="darwin")
        self.assertEqual(validate_cache(self.cache, self.repo, home=self.home, platform="darwin"), self.cache)
        self.assertFalse(self.cache.exists())

    def test_sync_path_cannot_be_hidden_by_a_symlink(self):
        (self.home / "alias").symlink_to(self.home / "Documents", target_is_directory=True)
        with self.assertRaises(StorageError):
            validate_cache(self.home / "alias/runs", self.repo, home=self.home, platform="darwin")

    def test_mac_case_aliases_cannot_enter_checkout_or_home(self):
        repo = self.base / "Repo"
        repo.mkdir()
        for candidate in (self.base / "rEPO/runs", self.base / "rEPO", self.base / "HOME"):
            with self.subTest(candidate=candidate):
                with self.assertRaises(StorageError):
                    validate_cache(candidate, repo, home=self.home, platform="darwin")

    def test_cache_inventory_refuses_symlinks_and_deduplicates_hardlinks(self):
        self.cache.mkdir(parents=True)
        original = self.cache / "original"
        original.write_bytes(b"some evidence")
        before = tree_bytes(self.cache)
        os.link(original, self.cache / "hardlink")
        self.assertEqual(tree_bytes(self.cache), before)
        (self.cache / "symlink").symlink_to(original)
        with self.assertRaisesRegex(StorageError, "unaccountable"):
            tree_bytes(self.cache)

    def test_admission_accounts_for_reservation_and_disk_headroom(self):
        with patch("noetloom.storage.shutil.disk_usage", return_value=SimpleNamespace(free=100)):
            self.policy["min_free_disk_bytes"] = 90
            self.assertEqual(storage_snapshot(self.cache, self.policy, 10)["reserved_bytes"], 10)
            with self.assertRaisesRegex(StorageError, "free disk"):
                storage_snapshot(self.cache, self.policy, 11)
        with self.assertRaisesRegex(StorageError, "workspace budget"):
            storage_snapshot(self.cache, self.policy, self.policy["max_workspace_bytes"] + 1)
        self.assertFalse(self.cache.exists())

    def test_atomic_pointer_rename_is_tolerated_only_by_live_sampling(self):
        self.cache.mkdir(parents=True)
        transient = self.cache / ".CURRENT-fixture"
        published = self.cache / "CURRENT"
        original = Path.lstat

        def raced(path, *args, **kwargs):
            if path == transient and transient.exists():
                os.replace(transient, published)
            return original(path, *args, **kwargs)

        transient.write_bytes(b"published pointer")
        with patch.object(Path, "lstat", raced), self.assertRaises(FileNotFoundError):
            tree_bytes(self.cache)
        published.unlink()
        transient.write_bytes(b"published pointer")
        with patch.object(Path, "lstat", raced):
            self.assertEqual(tree_bytes(self.cache, live=True), 0)
        # A live sample is approximate; the completed inventory must include CURRENT.
        self.assertEqual(published.read_bytes(), b"published pointer")
        self.assertGreaterEqual(tree_bytes(self.cache), len(b"published pointer"))

    def test_live_sampling_still_refuses_symlinks_and_unreadable_entries(self):
        self.cache.mkdir(parents=True)
        payload = self.cache / "payload"
        payload.write_bytes(b"evidence")
        link = self.cache / "link"
        link.symlink_to(payload)
        with self.assertRaisesRegex(StorageError, "unaccountable"):
            tree_bytes(self.cache, live=True)
        link.unlink()
        original = Path.lstat

        def denied(path, *args, **kwargs):
            if path == payload:
                raise PermissionError("unreadable entry")
            return original(path, *args, **kwargs)

        with patch.object(Path, "lstat", denied), self.assertRaises(PermissionError):
            tree_bytes(self.cache, live=True)

    def test_run_lease_serializes_and_releases_only_its_own_lock(self):
        with RunLease(self.cache, self.policy, 1024) as lease:
            original = lease.lock.read_bytes()
            with self.assertRaisesRegex(StorageError, "lock exists"):
                with RunLease(self.cache, self.policy, 1024):
                    self.fail("second writer entered")
            self.assertEqual(lease.lock.read_bytes(), original)
        self.assertFalse(lease.lock.exists())
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            with RunLease(self.cache, self.policy, 1024):
                raise RuntimeError("interrupted")
        self.assertFalse(lease.lock.exists())

    def test_lock_with_replaced_identity_is_preserved(self):
        with RunLease(self.cache, self.policy, 1024) as lease:
            lease.lock.rename(self.cache / "old-lock")
            lease.lock.write_text("replacement owner")
        self.assertEqual(lease.lock.read_text(), "replacement owner")

    def test_writer_refuses_output_before_crossing_byte_budget(self):
        writer = RunWriter(self.base / "run", 3, 5)
        path = writer.directory / "output"
        with path.open("xb") as handle:
            writer.append(handle, b"12")
            with self.assertRaisesRegex(StorageError, "output-byte"):
                writer.append(handle, b"34")
        self.assertEqual(path.read_bytes(), b"12")
        with self.assertRaises(FileExistsError):
            RunWriter(writer.directory, 3, 5)
        with self.assertRaises(StorageError):
            writer.write_json("../escape.json", {})

    def test_writer_enforces_cooperative_deadline(self):
        with patch("noetloom.storage.time.monotonic", return_value=100):
            writer = RunWriter(self.base / "timed-run", 100, 5)
        with patch("noetloom.storage.time.monotonic", return_value=106):
            with self.assertRaisesRegex(StorageError, "wall-clock"):
                writer.write_json("late.json", {})
