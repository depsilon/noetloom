from contextlib import closing
import csv
import io
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile

from toolshelf.storage import Store


ROOT = Path(__file__).resolve().parents[1]
HISTORY_COLUMNS = ["renewal_id", "loan_id", "asset_id", "old_due_on", "new_due_on", "renewed_on"]


def older_library(path, version):
    """An actual pre-renewal schema, with sparse IDs and a retained sequence."""
    asset = " Straße-1 " if version == 1 else "strasse-1"
    hammer = " H-1 " if version == 1 else "h-1"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("PRAGMA application_id = 1414744134")
        connection.execute(f"PRAGMA user_version = {version}")
        connection.execute("CREATE TABLE tools (asset_id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL)")
        connection.execute("""CREATE TABLE loans (
            loan_id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id TEXT NOT NULL REFERENCES tools(asset_id),
            borrower TEXT NOT NULL, lent_on TEXT NOT NULL,
            due_on TEXT NOT NULL CHECK(due_on >= lent_on),
            returned_on TEXT CHECK(returned_on IS NULL OR returned_on >= lent_on))""")
        connection.execute("CREATE UNIQUE INDEX one_active_loan ON loans(asset_id) WHERE returned_on IS NULL")
        connection.executemany("INSERT INTO tools VALUES (?, ?)", [(asset, "Perceuse — café"), (hammer, "Hammer")])
        connection.executemany("INSERT INTO loans VALUES (?, ?, ?, ?, ?, ?)", [
            (7, asset, "Previous borrower", "2026-09-01", "2026-09-25", "2026-09-20"),
            (19, asset, "Alex María", "2026-10-01", "2026-10-06", None),
        ])
        connection.execute("UPDATE sqlite_sequence SET seq = 40 WHERE name = 'loans'")


class RenewalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "evidence")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory / "library.sqlite3"
        self.store = Store(self.path)

    def command(self, *arguments):
        return [sys.executable, "-B", "-m", "toolshelf", "--db", str(self.path), *arguments]

    def cli(self, *arguments):
        return subprocess.run(self.command(*arguments), cwd=ROOT, text=True, capture_output=True, timeout=10)

    def success(self, *arguments, unchanged=False):
        before = self.path.read_bytes() if self.path.exists() else None
        result = self.cli(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        if unchanged:
            after = self.path.read_bytes() if self.path.exists() else None
            self.assertEqual(after, before)
        return result.stdout

    def reject(self, arguments, message, *, status=1):
        before = self.path.read_bytes() if self.path.exists() else None
        result = self.cli(*arguments)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        self.assertIn(message, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        after = self.path.read_bytes() if self.path.exists() else None
        self.assertEqual(after, before)

    def seed(self):
        self.success("add", " Straße-1 ", "Perceuse — café")
        self.success("add", "H-1", "Hammer")
        self.success("lend", "STRASSE-1", "Alex María", "--due", "2026-10-06", "--on", "2026-10-01")

    def history(self, *arguments):
        output = self.success("renewals", *arguments, unchanged=True)
        reader = csv.DictReader(io.StringIO(output), delimiter="\t")
        self.assertEqual(reader.fieldnames, HISTORY_COLUMNS)
        return list(reader)

    def test_cli_renewal_preserves_loan_and_updates_existing_reports(self):
        self.seed()
        original = self.store.loans()[0]
        confirmation = self.success("renew", "\t STRASSE-1 \n", "--due", "2026-10-10", "--on", "2026-10-07")
        self.assertIn("Renewal 1", confirmation)
        expected = {**original, "due_on": "2026-10-10"}
        self.assertEqual(self.store.loans(), [expected])
        self.assertEqual(self.store.loans(active_only=True), [expected])
        self.assertEqual(self.history(), [{
            "renewal_id": "1", "loan_id": "1", "asset_id": "strasse-1",
            "old_due_on": "2026-10-06", "new_due_on": "2026-10-10", "renewed_on": "2026-10-07",
        }])
        inventory = list(csv.DictReader(io.StringIO(self.success("inventory", unchanged=True)), delimiter="\t"))
        self.assertEqual(list(inventory[0]), ["asset_id", "name", "status", "borrower", "due_on"])
        self.assertEqual(inventory[1]["due_on"], "2026-10-10")
        for query_date in ("2026-09-30", "2026-10-07", "2026-10-10"):
            output = self.success("overdue", "--as-of", query_date, unchanged=True)
            self.assertEqual(len(output.splitlines()), 1)
        output = self.success("overdue", "--as-of", "2026-10-11", unchanged=True)
        self.assertIn("Alex María\t2026-10-01\t2026-10-10", output)
        self.assertEqual(output.splitlines()[0], "loan_id\tasset_id\tname\tborrower\tlent_on\tdue_on\treturned_on")

    def test_event_ids_order_and_history_survive_return_and_reborrow(self):
        self.seed()
        self.success("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-07")
        self.success("lend", "h-1", "Sam", "--due", "2026-10-06", "--on", "2026-10-01")
        self.success("renew", "h-1", "--due", "2026-10-08", "--on", "2026-10-07")
        self.success("renew", "strasse-1", "--due", "2026-10-12", "--on", "2026-10-07")
        self.success("return", "strasse-1", "--on", "2026-10-07")
        self.success("lend", "strasse-1", "Robin", "--due", "2026-10-09", "--on", "2026-10-08")
        self.success("renew", "strasse-1", "--due", "2026-10-11", "--on", "2026-10-08")
        rows = self.history()
        self.assertEqual([r["renewal_id"] for r in rows], ["1", "2", "3", "4"])
        self.assertEqual([r["loan_id"] for r in rows], ["1", "2", "1", "3"])
        self.assertEqual([r["old_due_on"] for r in rows], ["2026-10-06", "2026-10-06", "2026-10-10", "2026-10-09"])
        self.assertEqual(self.history("--asset", "\n STRASSE-1\t"), [rows[0], rows[2], rows[3]])
        self.assertEqual(self.history("--asset", "unknown"), [])
        self.assertEqual([r["loan_id"] for r in self.store.loans()], [1, 2, 3])
        self.assertEqual(self.store.loans()[0]["returned_on"], "2026-10-07")

    def test_invalid_renewals_leave_saved_bytes_unchanged(self):
        self.seed()
        cases = [
            (("renew", "unknown", "--due", "2026-10-10", "--on", "2026-10-07"), "Unknown asset"),
            (("renew", "h-1", "--due", "2026-10-10", "--on", "2026-10-07"), "no active loan"),
            (("renew", "strasse-1", "--due", "2026-10-06", "--on", "2026-10-02"), "later than"),
            (("renew", "strasse-1", "--due", "2026-10-05", "--on", "2026-10-02"), "later than"),
            (("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-09-30"), "lending date"),
            (("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-11"), "precede renewal date"),
            (("renew", " ", "--due", "2026-10-10", "--on", "2026-10-07"), "Asset ID"),
            (("renew", "strasse\n-1", "--due", "2026-10-10", "--on", "2026-10-07"), "control characters"),
            (("renewals", "--asset", ""), "Asset ID"),
        ]
        for command, error in cases:
            with self.subTest(command=command):
                self.reject(command, error)
        for bad in ("", " ", "2026-02-29", "2026-2-01", "20261001", "0000-10-01", "2026-10-01\n"):
            for option in ("--due", "--on"):
                arguments = ["renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-07"]
                arguments[arguments.index(option) + 1] = bad
                with self.subTest(option=option, value=bad):
                    self.reject(arguments, "real date")
        self.assertEqual(self.history(), [])

    def test_both_dates_are_required(self):
        self.seed()
        for arguments, missing in (
            (("renew", "strasse-1", "--due", "2026-10-10"), "--on"),
            (("renew", "strasse-1", "--on", "2026-10-07"), "--due"),
        ):
            self.reject(arguments, missing, status=2)

    def test_latest_renewal_limits_later_renewals_and_returns(self):
        self.seed()
        self.success("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-07")
        self.reject(("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-07"), "later than")
        self.reject(("renew", "strasse-1", "--due", "2026-10-12", "--on", "2026-10-06"), "latest renewal date")
        self.reject(("return", "strasse-1", "--on", "2026-10-06"), "latest renewal date")
        self.success("renew", "strasse-1", "--due", "2026-10-12", "--on", "2026-10-12")
        self.reject(("return", "strasse-1", "--on", "2026-10-11"), "latest renewal date")
        self.success("return", "strasse-1", "--on", "2026-10-12")
        self.reject(("renew", "strasse-1", "--due", "2026-10-15", "--on", "2026-10-13"), "no active loan")
        self.assertEqual(len(self.history()), 2)

    def test_missing_library_queries_and_rejected_renewal_create_nothing(self):
        self.assertEqual(self.history(), [])
        self.assertEqual(self.history("--asset", "strasse-1"), [])
        self.reject(("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-07"), "Unknown asset")
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_old_versions_read_without_rewriting_and_upgrade_only_on_valid_write(self):
        for version in (1, 2):
            with self.subTest(version=version):
                self.path = self.directory / f"v{version}.sqlite3"
                self.store = Store(self.path)
                older_library(self.path, version)
                self.assertEqual(self.history(), [])
                self.assertEqual(self.history("--asset", " Straße-1 "), [])
                for arguments in (("inventory",), ("loans",), ("loans", "--active"), ("overdue", "--as-of", "2026-10-07")):
                    self.success(*arguments, unchanged=True)
                original_loans = self.store.loans()
                for arguments, message in (
                    (("renew", "strasse-1", "--due", "2026-10-06", "--on", "2026-10-02"), "later than"),
                    (("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-09-30"), "lending date"),
                    (("renew", "h-1", "--due", "2026-10-10", "--on", "2026-10-07"), "no active loan"),
                    (("renew", "unknown", "--due", "2026-10-10", "--on", "2026-10-07"), "Unknown asset"),
                    (("add", "STRASSE-1", "Duplicate"), "already exists"),
                ):
                    self.reject(arguments, message)
                with closing(sqlite3.connect(self.path)) as connection:
                    self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], version)
                    self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name = 'renewals'").fetchone())
                self.success("renew", "\n STRASSE-1 \t", "--due", "2026-10-10", "--on", "2026-10-07")
                self.assertEqual(self.store.loans(), [original_loans[0], {**original_loans[1], "due_on": "2026-10-10"}])
                self.assertEqual(self.history()[0]["loan_id"], "19")
                self.success("return", "strasse-1", "--on", "2026-10-07")
                self.success("lend", "strasse-1", "Robin", "--due", "2026-10-10", "--on", "2026-10-08")
                self.assertEqual([r["loan_id"] for r in self.store.loans()], [7, 19, 41])
                with closing(sqlite3.connect(self.path)) as connection:
                    self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 3)
                    self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                    self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_legacy_collision_is_still_rejected_by_new_commands(self):
        older_library(self.path, 1)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("INSERT INTO tools VALUES ('STRASSE-1', 'Conflicting tool')")
        for arguments in (("renewals",), ("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-07")):
            self.reject(arguments, "collide after normalization")

    def test_storage_failure_rolls_back_event_and_any_schema_upgrade(self):
        for version in (2, 3):
            with self.subTest(version=version):
                self.path = self.directory / f"write-failure-v{version}.sqlite3"
                if version == 2:
                    older_library(self.path, version)
                else:
                    self.seed()
                # A real SQLite failure after event insertion challenges the whole
                # transaction, including the older-schema upgrade. No storage mock.
                with closing(sqlite3.connect(self.path)) as connection, connection:
                    connection.execute("""CREATE TRIGGER fail_due_update BEFORE UPDATE OF due_on ON loans
                        BEGIN SELECT RAISE(ABORT, 'Simulated due update failure'); END""")
                self.reject(("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-07"),
                            "Simulated due update failure")
                self.assertEqual(self.history(), [])
                with closing(sqlite3.connect(self.path)) as connection:
                    self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], version)
                    self.assertEqual(connection.execute("SELECT due_on FROM loans WHERE returned_on IS NULL").fetchone()[0],
                                     "2026-10-06")

    def test_new_commands_reject_foreign_and_unknown_versions_unchanged(self):
        for kind in ("foreign", "future"):
            self.path = self.directory / f"{kind}.sqlite3"
            with closing(sqlite3.connect(self.path)) as connection, connection:
                connection.execute("CREATE TABLE unrelated (value TEXT)")
                connection.execute("INSERT INTO unrelated VALUES ('preserve')")
                if kind == "future":
                    connection.execute("PRAGMA application_id = 1414744134")
                    connection.execute("PRAGMA user_version = 999")
            for arguments in (("renewals",), ("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-07")):
                with self.subTest(kind=kind, arguments=arguments):
                    self.reject(arguments, "not a ToolShelf database" if kind == "foreign" else "Unsupported")

    def competing(self, *commands):
        processes = [subprocess.Popen(self.command(*arguments), cwd=ROOT, text=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for arguments in commands]
        try:
            outputs = [process.communicate(timeout=10) for process in processes]
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        return [process.returncode for process in processes], outputs

    def test_competing_identical_renewals_create_exactly_one_event(self):
        for version in (1, 2, 3):
            with self.subTest(version=version):
                self.path = self.directory / f"competing-v{version}.sqlite3"
                self.store = Store(self.path)
                if version < 3:
                    older_library(self.path, version)
                else:
                    self.seed()
                arguments = ("renew", "STRASSE-1", "--due", "2026-10-10", "--on", "2026-10-07")
                statuses, outputs = self.competing(arguments, arguments)
                self.assertEqual(sorted(statuses), [0, 1], outputs)
                self.assertIn("later than", "".join(stderr for _, stderr in outputs))
                self.assertEqual(len(self.store.renewals()), 1)
                self.assertEqual(self.store.renewals()[0]["old_due_on"], "2026-10-06")
                self.assertEqual(self.store.loans(active_only=True)[0]["due_on"], "2026-10-10")

    def test_competing_different_extensions_form_one_serial_history(self):
        self.seed()
        statuses, outputs = self.competing(
            ("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-07"),
            ("renew", "STRASSE-1", "--due", "2026-10-12", "--on", "2026-10-07"),
        )
        self.assertIn(statuses, ([0, 0], [1, 0]), outputs)
        events = self.store.renewals()
        self.assertEqual(len(events), statuses.count(0))
        self.assertEqual(events[0]["old_due_on"], "2026-10-06")
        for previous, following in zip(events, events[1:]):
            self.assertEqual(previous["new_due_on"], following["old_due_on"])
            self.assertLess(previous["renewal_id"], following["renewal_id"])
        self.assertEqual(events[-1]["new_due_on"], "2026-10-12")
        self.assertEqual(self.store.loans()[0]["due_on"], "2026-10-12")

    def test_competing_renewal_and_earlier_return_cannot_both_commit(self):
        self.seed()
        statuses, outputs = self.competing(
            ("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-07"),
            ("return", "STRASSE-1", "--on", "2026-10-06"),
        )
        self.assertEqual(sorted(statuses), [0, 1], outputs)
        loan = self.store.loans()[0]
        if statuses[0] == 0:
            self.assertEqual((loan["due_on"], loan["returned_on"]), ("2026-10-10", ""))
            self.assertEqual(len(self.store.renewals()), 1)
            self.assertIn("latest renewal date", outputs[1][1])
        else:
            self.assertEqual((loan["due_on"], loan["returned_on"]), ("2026-10-06", "2026-10-06"))
            self.assertEqual(self.store.renewals(), [])
            self.assertIn("no active loan", outputs[0][1])

    def test_renewal_alone_keeps_actual_cli_catalog_preview_valid(self):
        self.seed()
        catalog = self.directory / "catalog.csv"
        catalog.write_text("asset_id,name\nsaw,Scie\n", encoding="utf-8")
        preview = self.success("import", str(catalog), unchanged=True)
        token = next(line.removeprefix("Preview token: ") for line in preview.splitlines()
                     if line.startswith("Preview token: "))
        self.success("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-07")
        renewed = self.history()
        self.success("import", str(catalog), "--confirm", token)
        self.assertEqual(self.history(), renewed)
        self.assertEqual([row["asset_id"] for row in self.store.inventory()], ["h-1", "saw", "strasse-1"])

    def test_export_old_versions_is_read_only_and_restores_upgraded_data(self):
        for version in (1, 2):
            with self.subTest(version=version):
                source = self.directory / f"source-v{version}.sqlite3"
                older_library(source, version)
                self.path = source
                expected = {arguments: self.success(*arguments, unchanged=True) for arguments in (
                    ("inventory",), ("loans",), ("renewals",), ("overdue", "--as-of", "2026-10-07"),
                )}
                archive_path = self.directory / f"v{version}.zip"
                self.success("export", str(archive_path), unchanged=True)
                with zipfile.ZipFile(archive_path) as archive:
                    self.assertEqual(archive.read("renewals.csv").decode("utf-8"), ",".join(HISTORY_COLUMNS) + "\n")
                    self.path = self.directory / f"restored-v{version}.sqlite3"
                    self.path.write_bytes(archive.read("library.sqlite3"))
                for arguments, output in expected.items():
                    self.assertEqual(self.success(*arguments, unchanged=True), output)
                self.success("renew", "strasse-1", "--due", "2026-10-10", "--on", "2026-10-07")
                self.assertEqual(self.history()[0]["loan_id"], "19")
                with closing(sqlite3.connect(self.path)) as connection:
                    self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
