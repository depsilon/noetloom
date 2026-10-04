from contextlib import closing
import csv
import io
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

from toolshelf.domain import ToolShelfError
from toolshelf.storage import Store
from toolshelf.transfer import apply_import, export_archive, preview_import


ROOT = Path(__file__).resolve().parents[1]


class TransferTests(unittest.TestCase):
    def test_csv_identity_trims_tabs_before_validation_and_collision_detection(self):
        self.write_csv("asset_id,name\n\t H-1 \t,Hammer\n")
        _, token = preview_import(self.store, self.csv_path)
        self.assertEqual(apply_import(self.store, self.csv_path, token), 1)
        self.assertEqual(self.store.inventory()[0]["asset_id"], "h-1")
        self.assert_invalid_batch("asset_id,name\n\t X \t,First\nx,Second\n", "duplicates line 2")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "evidence")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory / "library.sqlite3"
        self.csv_path = self.directory / "catalog.csv"
        self.store = Store(self.path)

    def command(self, *arguments, db=None):
        return [sys.executable, "-B", "-m", "toolshelf", "--db", str(db or self.path), *arguments]

    def cli(self, *arguments, db=None):
        return subprocess.run(self.command(*arguments, db=db), cwd=ROOT, text=True, capture_output=True, timeout=10)

    def write_csv(self, text, *, bom=False):
        self.csv_path.write_text(text, encoding="utf-8-sig" if bom else "utf-8", newline="")

    def assert_invalid_batch(self, text, *messages):
        self.write_csv(text)
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        for confirm in ((), ("--confirm", "0" * 64)):
            result = self.cli("import", str(self.csv_path), *confirm)
            self.assertEqual(result.returncode, 1, result.stdout)
            for message in messages:
                self.assertIn(message, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertNotIn("Preview token:", result.stdout)
            after = {path.name: path.read_bytes() for path in self.directory.iterdir()}
            self.assertEqual(after, before)

    def test_preview_then_confirmed_cli_import_with_bom_quoted_unicode(self):
        self.write_csv('asset_id,name\r\n D-1 ,"Perceuse, café ""électrique"""\r\nStraße-2,Équerre\r\n', bom=True)
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        result = self.cli("import", str(self.csv_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("d-1", result.stdout)
        self.assertIn("strasse-2", result.stdout)
        self.assertEqual({path.name: path.read_bytes() for path in self.directory.iterdir()}, before)
        token = next(line.removeprefix("Preview token: ") for line in result.stdout.splitlines()
                     if line.startswith("Preview token: "))
        result = self.cli("import", str(self.csv_path), "--confirm", token)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Imported 2", result.stdout)
        rows = self.store.inventory()
        self.assertEqual([(row["asset_id"], row["name"]) for row in rows],
                         [("d-1", 'Perceuse, café "électrique"'), ("strasse-2", "Équerre")])
        before = self.path.read_bytes()
        repeated = self.cli("import", str(self.csv_path), "--confirm", token)
        self.assertEqual(repeated.returncode, 1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_entire_batch_reports_recoverable_rows_and_writes_nothing(self):
        self.store.add("already", "Original")
        self.assert_invalid_batch(
            'asset_id,name\nvalid,Good\n X ,First\nx,Second\nmissing\nextra,Name,Oops\nblank, \n ALREADY ,Collision\n',
            "Line 4", "duplicates line 3", "Line 5", "Line 6", "Line 7", "Line 8", "already exists",
        )
        self.assertEqual([row["asset_id"] for row in self.store.inventory()], ["already"])

    def test_normalized_unicode_batch_collision_creates_no_database(self):
        self.assert_invalid_batch('asset_id,name\n Straße ,First\nSTRASSE,Second\nvalid,Good\n',
                                  "Line 3", "duplicates line 2")
        self.assertFalse(self.path.exists())

    def test_invalid_headers_encoding_quoting_and_single_line_contract(self):
        cases = (
            ("name,asset_id\nDrill,d-1\n", "headers must be exactly"),
            ("asset_id,name,extra\na,A,x\n", "headers must be exactly"),
            ("asset_id,name\n", "no catalog rows"),
            ('asset_id,name\nA,"Unclosed\n', "Line 2: malformed CSV"),
            ('asset_id,name\nA,"Drill"junk\n', "Line 2: malformed CSV"),
            ('asset_id,name\nA,"Multi\nline"\nB,\n', "Line 2"),
            ('asset_id,name\nA,"Multi\nline"\nB,\n', "Line 4"),
            ('asset_id,name\nA,"One\u2028two"\n', "single line"),
            ('asset_id,name\nA,"Tab\tname"\n', "control characters"),
        )
        for contents, message in cases:
            with self.subTest(contents=contents):
                self.assert_invalid_batch(contents, message)
        self.csv_path.write_bytes(b"asset_id,name\na,\xff\n")
        result = self.cli("import", str(self.csv_path))
        self.assertEqual(result.returncode, 1)
        self.assertIn("UTF-8", result.stderr)
        self.assertFalse(self.path.exists())

    def test_changed_file_bytes_reject_confirmation_even_with_same_parsed_values(self):
        self.write_csv("asset_id,name\na,Drill\n")
        _, token = preview_import(self.store, self.csv_path)
        self.write_csv("asset_id,name\na,Drill\r\n")
        result = self.cli("import", str(self.csv_path), "--confirm", token)
        self.assertEqual(result.returncode, 1)
        self.assertIn("stale", result.stderr)
        self.assertFalse(self.path.exists())
        self.assertEqual([p.name for p in self.directory.iterdir()], ["catalog.csv"])

    def test_changed_catalog_stales_preview_and_new_preview_can_apply(self):
        self.store.add("original", "Drill")
        self.write_csv("asset_id,name\na,Hammer\n")
        _, token = preview_import(self.store, self.csv_path)
        self.store.add("intervening", "Saw")
        before = self.path.read_bytes()
        result = self.cli("import", str(self.csv_path), "--confirm", token)
        self.assertEqual(result.returncode, 1)
        self.assertIn("stale", result.stderr)
        self.assertEqual(self.path.read_bytes(), before)
        _, current_token = preview_import(self.store, self.csv_path)
        self.assertNotEqual(token, current_token)
        self.assertEqual(apply_import(self.store, self.csv_path, current_token), 1)

    def test_changes_to_loans_do_not_stale_unchanged_catalog_preview(self):
        self.store.add("original", "Drill")
        self.write_csv("asset_id,name\na,Hammer\n")
        _, token = preview_import(self.store, self.csv_path)
        self.store.lend("original", "Alex", "2026-10-06", "2026-10-01")
        self.assertEqual(apply_import(self.store, self.csv_path, token), 1)
        self.assertEqual(len(self.store.loans()), 1)

    def test_confirmation_requires_real_preview_and_creates_no_file(self):
        self.write_csv("asset_id,name\na,Hammer\n")
        for token in ("", "yes", "0" * 64):
            result = self.cli("import", str(self.csv_path), "--confirm", token)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(self.path.exists())

    def test_concurrent_confirmations_cannot_import_twice(self):
        self.store.add("original", "Drill")
        self.write_csv("asset_id,name\na,Hammer\nb,Saw\n")
        _, token = preview_import(self.store, self.csv_path)
        processes = [subprocess.Popen(
            self.command("import", str(self.csv_path), "--confirm", token), cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ) for _ in range(2)]
        outputs = [process.communicate(timeout=10) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1], outputs)
        self.assertEqual([row["asset_id"] for row in self.store.inventory()], ["a", "b", "original"])

    def test_export_is_complete_restorable_and_catalog_round_trips(self):
        self.store.add("D-1", 'Perceuse, café "électrique"')
        self.store.add("H-1", "=RAW-TEXT")
        self.store.lend("d-1", "Alex, María", "2026-10-06", "2026-10-01")
        self.store.renew("d-1", "2026-10-08", "2026-10-02")
        self.store.return_tool(" D-1 ", "2026-10-03")
        self.store.lend("D-1", "Sam", "2026-10-09", "2026-10-04")
        self.store.renew("d-1", "2026-10-10", "2026-10-05")
        before = self.path.read_bytes()
        archive_path = self.directory / "recovery.zip"
        result = self.cli("export", str(archive_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.path.read_bytes(), before)
        with zipfile.ZipFile(archive_path) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()),
                             {"catalog.csv", "inventory.csv", "loans.csv", "renewals.csv", "library.sqlite3", "RESTORE.txt"})
            inventory = list(csv.DictReader(io.StringIO(archive.read("inventory.csv").decode("utf-8"))))
            loans = list(csv.DictReader(io.StringIO(archive.read("loans.csv").decode("utf-8"))))
            renewals = list(csv.DictReader(io.StringIO(archive.read("renewals.csv").decode("utf-8"))))
            self.assertEqual(inventory, self.store.inventory())
            self.assertEqual(loans, [{key: str(value) for key, value in row.items()} for row in self.store.loans()])
            self.assertEqual(renewals, [{key: str(value) for key, value in row.items()} for row in self.store.renewals()])
            self.assertEqual([row["renewal_id"] for row in renewals], ["1", "2"])
            restored = self.directory / "restored.sqlite3"
            restored.write_bytes(archive.read("library.sqlite3"))
            self.csv_path.write_bytes(archive.read("catalog.csv"))
        for command in (("inventory",), ("loans",), ("renewals",), ("renewals", "--asset", " D-1 "),
                        ("overdue", "--as-of", "2026-10-11")):
            expected = self.cli(*command)
            actual = self.cli(*command, db=restored)
            self.assertEqual(actual.returncode, 0, actual.stderr)
            self.assertEqual(actual.stdout, expected.stdout)
        with closing(sqlite3.connect(restored)) as connection, connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        copied = Store(self.directory / "catalog-copy.sqlite3")
        _, token = preview_import(copied, self.csv_path)
        apply_import(copied, self.csv_path, token)
        self.assertEqual([(r["asset_id"], r["name"]) for r in copied.inventory()],
                         [(r["asset_id"], r["name"]) for r in self.store.inventory()])

    def test_export_never_overwrites_existing_file(self):
        self.store.add("A", "Drill")
        existing = self.directory / "existing.zip"
        existing.write_bytes(b"Preserve this exact data")
        for destination in (existing, self.path):
            before = destination.read_bytes()
            result = self.cli("export", str(destination))
            self.assertEqual(result.returncode, 1)
            self.assertIn("already exists", result.stderr)
            self.assertEqual(destination.read_bytes(), before)

    @unittest.skipIf(os.name == "nt", "Unprivileged Windows symlink creation is host-dependent")
    def test_export_never_overwrites_symlink(self):
        existing = self.directory / "existing.zip"
        existing.write_bytes(b"Preserve this exact data")
        link = self.directory / "linked.zip"
        link.symlink_to(existing)
        result = self.cli("export", str(link))
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(existing.read_bytes(), b"Preserve this exact data")

    def test_export_cannot_publish_a_zip_at_the_absent_database_path(self):
        result = self.cli("export", str(self.path))
        self.assertEqual(result.returncode, 1)
        self.assertIn("must differ", result.stderr)
        self.assertFalse(self.path.exists())
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_competing_exports_publish_one_complete_archive_without_temporary_files(self):
        self.store.add("A", "Drill")
        destination = self.directory / "shared.zip"
        processes = [subprocess.Popen(self.command("export", str(destination)), cwd=ROOT,
                                     text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for _ in range(2)]
        outputs = [process.communicate(timeout=10) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1], outputs)
        with zipfile.ZipFile(destination) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read("catalog.csv").decode("utf-8"), "asset_id,name\na,Drill\n")
        self.assertEqual({path.name for path in self.directory.iterdir()}, {"shared.zip", "library.sqlite3"})

    def test_export_failure_cleans_temporary_files(self):
        self.path.write_bytes(b"not a database")
        before = set(self.directory.iterdir())
        result = self.cli("export", str(self.directory / "recovery.zip"))
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(set(self.directory.iterdir()), before)

    def test_export_of_absent_database_is_read_only_and_restorable(self):
        archive_path = self.directory / "empty.zip"
        export_archive(self.store, archive_path)
        self.assertFalse(self.path.exists())
        with zipfile.ZipFile(archive_path) as archive:
            restored = self.directory / "restored.sqlite3"
            restored.write_bytes(archive.read("library.sqlite3"))
        self.assertEqual(Store(restored).inventory(), [])
        self.assertEqual(Store(restored).loans(), [])
        self.assertEqual(Store(restored).renewals(), [])

    def test_missing_csv_or_parent_paths_are_clear_errors(self):
        for arguments in (
            ("import", str(self.directory / "missing.csv")),
            ("export", str(self.directory / "missing" / "export.zip")),
        ):
            result = self.cli(*arguments)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(self.path.exists())

    def test_legacy_preview_export_and_apply_preserve_atomic_normalization(self):
        self.store.add("d-1", "Drill")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("DROP TABLE renewals")
            connection.execute("UPDATE tools SET asset_id = ' D-1 '")
            connection.execute("PRAGMA user_version = 1")
        self.write_csv("asset_id,name\nH-1,Hammer\n")
        before = self.path.read_bytes()
        _, token = preview_import(self.store, self.csv_path)
        self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaisesRegex(ToolShelfError, "stale"):
            apply_import(self.store, self.csv_path, "0" * 64)
        self.assertEqual(self.path.read_bytes(), before)
        archive_path = self.directory / "legacy.zip"
        result = self.cli("export", str(archive_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.path.read_bytes(), before)
        with zipfile.ZipFile(archive_path) as archive:
            self.assertIn("d-1,Drill", archive.read("catalog.csv").decode("utf-8"))
        apply_import(self.store, self.csv_path, token)
        self.assertEqual([row["asset_id"] for row in self.store.inventory()], ["d-1", "h-1"])
        with closing(sqlite3.connect(self.path)) as connection, connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 3)

    def test_export_remains_consistent_during_separate_process_writes(self):
        self.store.add("a", "Drill")
        ready = self.directory / "writer-ready"
        stop = self.directory / "writer-stop"
        worker_code = """
from pathlib import Path
import sys
from toolshelf.storage import Store
store = Store(sys.argv[1])
for index in range(500):
    store.lend('a', f'Borrower {index}', '2026-10-06', '2026-10-01')
    store.renew('a', '2026-10-07', '2026-10-02')
    Path(sys.argv[2]).touch()
    store.return_tool('a', '2026-10-02')
    if Path(sys.argv[3]).exists():
        break
"""
        worker = subprocess.Popen([sys.executable, "-B", "-c", worker_code, str(self.path), str(ready), str(stop)],
                                  cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and worker.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(ready.exists(), "Concurrent writer did not start")
            archive_path = self.directory / "concurrent.zip"
            export_archive(self.store, archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                restored = self.directory / "restored.sqlite3"
                restored.write_bytes(archive.read("library.sqlite3"))
                saved = Store(restored)
                inventory = list(csv.DictReader(io.StringIO(archive.read("inventory.csv").decode("utf-8"))))
                loans = list(csv.DictReader(io.StringIO(archive.read("loans.csv").decode("utf-8"))))
                renewals = list(csv.DictReader(io.StringIO(archive.read("renewals.csv").decode("utf-8"))))
                self.assertEqual(inventory, saved.inventory())
                self.assertEqual(loans, [{key: str(value) for key, value in row.items()} for row in saved.loans()])
                self.assertEqual(renewals, [{key: str(value) for key, value in row.items()} for row in saved.renewals()])
                self.assertGreater(len(loans), 0)
                self.assertGreater(len(renewals), 0)
                for renewal in renewals:
                    loan = next(row for row in loans if row["loan_id"] == renewal["loan_id"])
                    self.assertEqual(loan["due_on"], renewal["new_due_on"])
        finally:
            stop.touch()
            try:
                stdout, stderr = worker.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.communicate()
                raise
        self.assertEqual(worker.returncode, 0, stderr)


if __name__ == "__main__":
    unittest.main()
