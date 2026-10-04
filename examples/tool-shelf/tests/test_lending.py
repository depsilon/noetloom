from datetime import date
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from toolshelf.storage import Store


ROOT = Path(__file__).resolve().parents[1]


class LendingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "evidence")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "library.sqlite3"
        self.store = Store(self.path)
        self.store.add(" Drill-1 ", "Perceuse — café")
        self.store.add("H-1", "Hammer")

    def command(self, *arguments):
        return [sys.executable, "-B", "-m", "toolshelf", "--db", str(self.path), *arguments]

    def cli(self, *arguments):
        return subprocess.run(self.command(*arguments), cwd=ROOT, text=True, capture_output=True, timeout=10)

    def assert_failure_unchanged(self, arguments, message):
        before = self.path.read_bytes()
        result = self.cli(*arguments)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(message, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.path.read_bytes(), before)

    def test_real_process_lifecycle_preserves_history_and_canonical_identity(self):
        result = self.cli("lend", " DRILL-1 ", " Alex María ", "--due", "2026-10-06", "--on", "2026-10-01")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Loan 1", result.stdout)
        available = self.cli("inventory", "--available")
        self.assertIn("h-1\tHammer", available.stdout)
        self.assertNotIn("drill-1", available.stdout)
        self.assertEqual(self.store.inventory()[0]["borrower"], "Alex María")
        result = self.cli("return", " DrIlL-1 ", "--on", "2026-10-04")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli("lend", "DRILL-1", "Sam", "--due", "2026-10-09", "--on", "2026-10-05")
        self.assertEqual(result.returncode, 0, result.stderr)
        history = self.store.loans()
        self.assertEqual([r["loan_id"] for r in history], [1, 2])
        self.assertEqual([r["returned_on"] for r in history], ["2026-10-04", ""])
        self.assertEqual([r["loan_id"] for r in self.store.loans(active_only=True)], [2])
        result = self.cli("loans")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 3)

    def test_invalid_transitions_leave_all_saved_bytes_unchanged(self):
        invalid = (
            (("lend", "missing", "Alex", "--due", "2026-10-06", "--on", "2026-10-01"), "Unknown asset"),
            (("return", "missing", "--on", "2026-10-01"), "Unknown asset"),
            (("return", "drill-1", "--on", "2026-10-01"), "no active loan"),
            (("lend", "drill-1", " ", "--due", "2026-10-06", "--on", "2026-10-01"), "Borrower"),
            (("lend", "drill-1", "Alex", "--due", "2026-09-30", "--on", "2026-10-01"), "precede"),
            (("lend", "drill-1", "Alex", "--due", "2026-02-29", "--on", "2026-10-01"), "real date"),
            (("lend", "drill-1", "Alex", "--due", "2026-10-06", "--on", "2026-1-01"), "real date"),
            (("lend", "drill-1", "Alex", "--due", "2026-10-06", "--on", ""), "real date"),
        )
        for arguments, message in invalid:
            with self.subTest(arguments=arguments):
                self.assert_failure_unchanged(arguments, message)
        self.store.lend("drill-1", "Alex", "2026-10-06", "2026-10-01")
        self.assert_failure_unchanged(
            ("lend", " DRILL-1 ", "Sam", "--due", "2026-10-09", "--on", "2026-10-02"), "already loaned")
        self.assert_failure_unchanged(("return", "drill-1", "--on", "2026-09-30"), "precede")
        self.assert_failure_unchanged(("return", "drill-1", "--on", "2026-02-30"), "real date")
        self.store.return_tool("DRILL-1", "2026-10-01")
        self.assert_failure_unchanged(("return", "drill-1", "--on", "2026-10-02"), "no active loan")

    def test_overdue_requires_date_and_is_exclusive_and_stably_ordered(self):
        self.store.lend("drill-1", "Alex", "2026-10-06", "2026-10-01")
        self.store.lend("h-1", "Sam", "2026-10-05", "2026-10-01")
        self.assertEqual(self.store.loans(as_of="2026-09-30"), [])
        self.assertEqual(self.store.loans(as_of="2026-10-05"), [])
        self.assertEqual([r["asset_id"] for r in self.store.loans(as_of="2026-10-06")], ["h-1"])
        self.assertEqual([r["loan_id"] for r in self.store.loans(as_of="2026-10-07")], [2, 1])
        self.assert_failure_unchanged(("overdue",), "--as-of")
        self.assert_failure_unchanged(("overdue", "--as-of", "yesterday"), "real date")
        self.store.return_tool("h-1", "2026-10-07")
        self.assertEqual(self.store.loans(as_of="2026-10-06"), [])

    def test_default_lending_and_return_date_is_today(self):
        today = date.today().isoformat()
        result = self.cli("lend", "drill-1", "Alex", "--due", today)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli("return", "drill-1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.store.loans()[0]["lent_on"], today)
        self.assertEqual(self.store.loans()[0]["returned_on"], today)

    def test_separate_competing_processes_cannot_double_lend(self):
        processes = [subprocess.Popen(
            self.command("lend", identifier, borrower, "--due", "2026-10-06", "--on", "2026-10-01"),
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ) for identifier, borrower in ((" DRILL-1 ", "Alex"), ("drill-1", "Sam"))]
        outputs = [process.communicate(timeout=10) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1], outputs)
        self.assertEqual(len(self.store.loans()), 1)
        self.assertIn("already loaned", "".join(stderr for _, stderr in outputs))
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_unknown_asset_on_missing_database_does_not_create_files(self):
        self.path = Path(self.temporary.name) / "missing.sqlite3"
        before = set(self.path.parent.iterdir())
        for arguments in (
            ("lend", "x", "Alex", "--due", "2026-10-06", "--on", "2026-10-01"),
            ("return", "x", "--on", "2026-10-01"),
            ("loans",), ("overdue", "--as-of", "2026-10-07"),
        ):
            result = self.cli(*arguments)
            self.assertEqual(result.returncode, 1 if arguments[0] in ("lend", "return") else 0, result.stderr)
            self.assertEqual(set(self.path.parent.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
