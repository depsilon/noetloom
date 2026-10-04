from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from toolshelf.domain import ToolShelfError, calendar_date
from toolshelf.storage import Store


ROOT = Path(__file__).resolve().parents[1]


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "evidence")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "library.sqlite3"
        self.store = Store(self.path)

    def cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-B", "-m", "toolshelf", "--db", str(self.path), *arguments],
            cwd=ROOT, text=True, capture_output=True, check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            timeout=10,
        )

    def test_catalog_survives_separate_processes(self):
        for asset, name in (("D-1", "Cordless drill"), ("H-1", "Claw hammer")):
            result = self.cli("add", asset, name)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli("inventory", "--available")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("d-1\tCordless drill\tavailable", result.stdout)
        self.assertIn("h-1\tClaw hammer\tavailable", result.stdout)

    def test_duplicate_cannot_replace_original(self):
        self.store.add("D-1", "Drill")
        before = self.path.read_bytes()
        result = self.cli("add", " d-1 ", "Replacement")
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(Store(self.path).inventory()[0]["name"], "Drill")

    def test_surrounding_whitespace_is_trimmed_at_each_cli_id_boundary(self):
        commands = (
            ("add", "\tD-1\r\n", "Drill"),
            ("lend", "\n d-1\t", "Alex", "--due", "2026-10-06", "--on", "2026-10-01"),
            ("return", "\r D-1 \n", "--on", "2026-10-03"),
        )
        for command in commands:
            result = self.cli(*command)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.store.inventory()[0]["asset_id"], "d-1")
        self.assertEqual(self.store.loans()[0]["returned_on"], "2026-10-03")

    def test_invalid_text_never_creates_database(self):
        for asset, name in (("", "Drill"), ("A", "  "), ("A\tB", "Drill"), ("A", "Drill\n")):
            with self.subTest(asset=asset, name=name):
                with self.assertRaises(ToolShelfError):
                    self.store.add(asset, name)
                self.assertFalse(self.path.exists())

    def test_empty_read_is_successful_and_does_not_create_database(self):
        result = self.cli("inventory")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertFalse(self.path.exists())

    def test_ids_casefold_and_names_preserve_unicode(self):
        self.store.add(" Straße-1 ", " Perceuse — café ")
        with self.assertRaisesRegex(ToolShelfError, "already exists"):
            self.store.add(" STRASSE-1 ", "Second drill")
        self.assertEqual([(r["asset_id"], r["name"]) for r in self.store.inventory()],
                         [("strasse-1", "Perceuse — café")])

    def legacy_database(self, assets):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("PRAGMA application_id = 1414744134")
            connection.execute("PRAGMA user_version = 1")
            connection.execute("CREATE TABLE tools (asset_id TEXT PRIMARY KEY, name TEXT NOT NULL)")
            connection.execute("""CREATE TABLE loans (loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id TEXT REFERENCES tools(asset_id), borrower TEXT, lent_on TEXT,
                due_on TEXT, returned_on TEXT)""")
            connection.execute("CREATE UNIQUE INDEX one_active_loan ON loans(asset_id) WHERE returned_on IS NULL")
            connection.executemany("INSERT INTO tools VALUES (?, ?)", assets)

    def test_legacy_read_is_canonical_and_write_migrates_atomically(self):
        self.legacy_database([(" D-1 ", "Drill")])
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("INSERT INTO loans VALUES (1, ' D-1 ', 'Alex', '2026-01-01', '2026-01-02', NULL)")
        before = self.path.read_bytes()
        self.assertEqual(self.store.inventory()[0]["asset_id"], "d-1")
        self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaises(ToolShelfError):
            self.store.add("d-1", "Duplicate")
        self.assertEqual(self.path.read_bytes(), before)
        self.store.add("H-1", "Hammer")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 3)
            self.assertEqual(connection.execute("SELECT asset_id FROM loans").fetchone()[0], "d-1")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_legacy_collisions_are_rejected_without_writes(self):
        self.legacy_database([("D-1", "Drill"), ("d-1", "Different drill")])
        before = self.path.read_bytes()
        for arguments in (("inventory",), ("add", "H-1", "Hammer")):
            result = self.cli(*arguments)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("collide after normalization", result.stderr)
            self.assertEqual(self.path.read_bytes(), before)

    def test_foreign_database_is_rejected_without_changes(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TABLE unrelated(secret TEXT)")
            connection.execute("INSERT INTO unrelated VALUES ('keep me')")
        before = self.path.read_bytes()
        for arguments in (("inventory",), ("add", "A", "Drill")):
            result = self.cli(*arguments)
            self.assertEqual(result.returncode, 1)
            self.assertIn("not a ToolShelf database", result.stderr)
            self.assertEqual(self.path.read_bytes(), before)

    def test_unknown_schema_version_is_rejected(self):
        self.store.add("A", "Drill")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("PRAGMA user_version = 999")
        result = self.cli("add", "B", "Hammer")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unsupported", result.stderr)

    def test_malformed_file_is_reported_without_traceback(self):
        self.path.write_text("not a database", encoding="utf-8")
        result = self.cli("inventory")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_dates_are_strict_real_calendar_dates(self):
        self.assertEqual(calendar_date("2024-02-29", "Date"), "2024-02-29")
        for value in ("2025-02-29", "2025-2-01", "20251001", "0000-01-01", "2025-13-01"):
            with self.subTest(value=value), self.assertRaises(ToolShelfError):
                calendar_date(value, "Date")

    def test_missing_database_parent_is_an_error_without_created_files(self):
        self.path = self.path.parent / "missing" / "library.sqlite3"
        for arguments in (("inventory",), ("add", "A", "Drill")):
            result = self.cli(*arguments)
            self.assertEqual(result.returncode, 1)
            self.assertIn("parent directory does not exist", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(self.path.parent.exists())


if __name__ == "__main__":
    unittest.main()
