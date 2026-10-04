"""Independent public-interface acceptance for the existing ToolShelf change.

This runner is authored outside the implementation workspace from acceptance-cases.md.
It does not import candidate implementation modules or the candidate's own tests.
"""
from contextlib import closing
import argparse
import csv
import io
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile


PROJECT = None
BASELINE = None
INVENTORY = ["asset_id", "name", "status", "borrower", "due_on"]
LOANS = ["loan_id", "asset_id", "name", "borrower", "lent_on", "due_on", "returned_on"]
RENEWALS = ["renewal_id", "loan_id", "asset_id", "old_due_on", "new_due_on", "renewed_on"]
REPORTS = [
    ("inventory",),
    ("inventory", "--available"),
    ("loans",),
    ("loans", "--active"),
    ("overdue", "--as-of", "2026-10-08"),
]


class IndependentAcceptance(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="toolshelf-independent-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.db = self.directory / "library.sqlite3"
        self.seed(self.db)

    def seed(self, path, *, version=2, collision=False):
        """A frozen legacy fixture, not generated through the candidate's model."""
        asset = " Straße-1 " if version == 1 else "strasse-1"
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.executescript("""
                CREATE TABLE tools (
                    asset_id TEXT PRIMARY KEY NOT NULL CHECK(length(trim(asset_id)) > 0),
                    name TEXT NOT NULL CHECK(length(trim(name)) > 0)
                );
                CREATE TABLE loans (
                    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id TEXT NOT NULL REFERENCES tools(asset_id),
                    borrower TEXT NOT NULL CHECK(length(trim(borrower)) > 0),
                    lent_on TEXT NOT NULL,
                    due_on TEXT NOT NULL CHECK(due_on >= lent_on),
                    returned_on TEXT CHECK(returned_on IS NULL OR returned_on >= lent_on)
                );
                CREATE UNIQUE INDEX one_active_loan ON loans(asset_id) WHERE returned_on IS NULL;
                PRAGMA application_id = 1414744134;
            """)
            connection.execute(f"PRAGMA user_version = {version}")
            connection.executemany("INSERT INTO tools VALUES (?, ?)", [
                (asset, "Perceuse — café"), ("hist-1", "Old saw"), ("spare-1", "Claw hammer"),
            ])
            if collision:
                connection.execute("INSERT INTO tools VALUES ('STRASSE-1', 'Collision')")
            connection.executemany("INSERT INTO loans VALUES (?, ?, ?, ?, ?, ?)", [
                (4, "hist-1", "Pat", "2026-09-01", "2026-09-15", "2026-09-10"),
                (7, asset, "Zoë", "2026-10-01", "2026-10-07", None),
            ])

    def arguments(self, arguments, db=None):
        return [sys.executable, "-B", "-m", "toolshelf", "--db", str(db or self.db), *arguments]

    def environment(self):
        return {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1"}

    def run_cli(self, *arguments, db=None, baseline=False, success=True):
        result = subprocess.run(
            self.arguments(arguments, db), cwd=BASELINE if baseline else PROJECT,
            env=self.environment(), stdin=subprocess.DEVNULL, capture_output=True,
            encoding="utf-8", timeout=20,
        )
        message = f"{arguments!r}\nexit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        if success:
            self.assertEqual(result.returncode, 0, message)
        else:
            self.assertNotEqual(result.returncode, 0, message)
            self.assertNotIn("Traceback", result.stderr, message)
        return result

    def rows(self, *arguments, columns=None, db=None, baseline=False):
        result = self.run_cli(*arguments, db=db, baseline=baseline)
        reader = csv.DictReader(io.StringIO(result.stdout), delimiter="\t")
        if columns is not None:
            self.assertEqual(reader.fieldnames, columns, result.stdout)
        return list(reader)

    def history(self, *, db=None, asset=None):
        arguments = ["renewals"]
        if asset is not None:
            arguments += ["--asset", asset]
        return self.rows(*arguments, columns=RENEWALS, db=db)

    def saved_bytes(self, directory=None):
        return {p.relative_to(directory or self.directory).as_posix(): p.read_bytes()
                for p in (directory or self.directory).rglob("*") if p.is_file()}

    def reject_unchanged(self, *arguments, db=None):
        before = self.saved_bytes()
        self.run_cli(*arguments, db=db, success=False)
        self.assertEqual(self.saved_bytes(), before, arguments)

    def check_integrity(self, db=None):
        with closing(sqlite3.connect(db or self.db)) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_legacy_v2_reports_and_read_only_history_preserve_bytes(self):
        expected = {command: self.run_cli(*command, baseline=True).stdout for command in REPORTS}
        before = self.db.read_bytes()
        for command, output in expected.items():
            with self.subTest(command=command):
                self.assertEqual(self.run_cli(*command).stdout, output)
        self.assertEqual(self.history(), [])
        self.assertEqual(self.history(asset=" STRASSE-1 "), [])
        self.assertEqual(self.db.read_bytes(), before)
        destination = self.directory / "legacy-read-export.zip"
        self.run_cli("export", str(destination))
        self.assertEqual(self.db.read_bytes(), before)
        with zipfile.ZipFile(destination) as archive:
            self.assertIn("renewals.csv", archive.namelist())
            reader = csv.DictReader(io.StringIO(archive.read("renewals.csv").decode("utf-8")))
            self.assertEqual(reader.fieldnames, RENEWALS)
            self.assertEqual(list(reader), [])

    def test_valid_v1_data_reads_without_writes_then_renews_preserving_loan_identity(self):
        legacy = self.directory / "legacy-v1.sqlite3"
        self.seed(legacy, version=1)
        expected = {command: self.run_cli(*command, db=legacy, baseline=True).stdout for command in REPORTS}
        before = legacy.read_bytes()
        for command, output in expected.items():
            self.assertEqual(self.run_cli(*command, db=legacy).stdout, output)
        self.assertEqual(self.history(db=legacy), [])
        self.assertEqual(legacy.read_bytes(), before)
        self.run_cli("renew", "\tStraße-1\n", "--due", "2026-10-15", "--on", "2026-10-05", db=legacy)
        events = self.history(db=legacy)
        self.assertEqual(len(events), 1)
        self.assertEqual({key: events[0][key] for key in RENEWALS[1:]}, {
            "loan_id": "7", "asset_id": "strasse-1", "old_due_on": "2026-10-07",
            "new_due_on": "2026-10-15", "renewed_on": "2026-10-05",
        })
        loans = self.rows("loans", columns=LOANS, db=legacy)
        self.assertEqual([r["loan_id"] for r in loans], ["4", "7"])
        self.assertEqual(loans[1]["borrower"], "Zoë")
        self.assertEqual(loans[1]["lent_on"], "2026-10-01")
        self.check_integrity(legacy)

    def test_two_renewals_keep_history_normalization_and_exact_overdue_boundary(self):
        self.run_cli("renew", "\tSTRAẞE-1\n", "--due", "2026-10-10", "--on", "2026-10-05")
        self.run_cli("renew", " strasse-1 ", "--due", "2026-10-20", "--on", "2026-10-12")
        history = self.history(asset=" Straße-1 ")
        self.assertEqual([(r["loan_id"], r["asset_id"], r["old_due_on"], r["new_due_on"], r["renewed_on"])
                          for r in history], [
            ("7", "strasse-1", "2026-10-07", "2026-10-10", "2026-10-05"),
            ("7", "strasse-1", "2026-10-10", "2026-10-20", "2026-10-12"),
        ])
        ids = [int(r["renewal_id"]) for r in history]
        self.assertEqual(ids, sorted(set(ids)))
        active = self.rows("loans", "--active", columns=LOANS)
        self.assertEqual([(r["loan_id"], r["borrower"], r["lent_on"], r["due_on"]) for r in active],
                         [("7", "Zoë", "2026-10-01", "2026-10-20")])
        self.assertEqual(self.rows("overdue", "--as-of", "2026-10-20", columns=LOANS), [])
        self.assertEqual([r["loan_id"] for r in self.rows("overdue", "--as-of", "2026-10-21", columns=LOANS)], ["7"])
        inventory = self.rows("inventory", columns=INVENTORY)
        self.assertEqual(next(r for r in inventory if r["asset_id"] == "strasse-1")["due_on"], "2026-10-20")
        self.check_integrity()

    def test_rejected_requests_and_early_returns_are_byte_atomic(self):
        arguments = [
            ("renew", "strasse-1", "--due", "2026-10-07", "--on", "2026-10-05"),
            ("renew", "strasse-1", "--due", "2026-10-06", "--on", "2026-10-05"),
            ("renew", "strasse-1", "--due", "", "--on", "2026-10-05"),
            ("renew", "strasse-1", "--due", "2026-02-30", "--on", "2026-10-05"),
            ("renew", "strasse-1", "--due", "2026-10-15", "--on", ""),
            ("renew", "strasse-1", "--due", "2026-10-15", "--on", "2026-09-30"),
            ("renew", "strasse-1", "--due", "2026-10-15", "--on", "2026-10-16"),
            ("renew", "missing", "--due", "2026-10-15", "--on", "2026-10-05"),
            ("renew", "spare-1", "--due", "2026-10-15", "--on", "2026-10-05"),
            ("renew", "strasse-1", "--due", "2026-10-15"),
        ]
        for command in arguments:
            with self.subTest(command=command):
                self.reject_unchanged(*command)
        self.run_cli("renew", "strasse-1", "--due", "2026-10-15", "--on", "2026-10-05")
        for command in [
            ("renew", "strasse-1", "--due", "2026-10-15", "--on", "2026-10-05"),
            ("renew", "strasse-1", "--due", "2026-10-20", "--on", "2026-10-04"),
            ("return", "strasse-1", "--on", "2026-10-04"),
        ]:
            with self.subTest(command=command):
                self.reject_unchanged(*command)
        self.assertEqual(len(self.history()), 1)

    def test_return_and_reborrow_preserve_prior_loan_and_renewal_history(self):
        self.run_cli("renew", "strasse-1", "--due", "2026-10-15", "--on", "2026-10-05")
        first = self.history()
        self.run_cli("return", " STRASSE-1 ", "--on", "2026-10-06")
        self.reject_unchanged("renew", "strasse-1", "--due", "2026-10-20", "--on", "2026-10-07")
        self.run_cli("lend", "strasse-1", "Alex", "--due", "2026-10-09", "--on", "2026-10-07")
        self.run_cli("renew", "strasse-1", "--due", "2026-10-12", "--on", "2026-10-08")
        all_history = self.history(asset="\tStraße-1\n")
        self.assertEqual(all_history[:1], first)
        self.assertEqual([r["loan_id"] for r in all_history], ["7", "8"])
        loans = {row["loan_id"]: row for row in self.rows("loans", columns=LOANS)}
        self.assertEqual((loans["7"]["due_on"], loans["7"]["returned_on"]), ("2026-10-15", "2026-10-06"))
        self.assertEqual((loans["8"]["borrower"], loans["8"]["due_on"]), ("Alex", "2026-10-12"))
        self.assertEqual(loans["4"]["returned_on"], "2026-09-10")
        self.check_integrity()

    def test_competing_identical_extensions_record_one_transition(self):
        arguments = ("renew", "strasse-1", "--due", "2026-10-15", "--on", "2026-10-05")
        processes = [subprocess.Popen(
            self.arguments(arguments), cwd=PROJECT, env=self.environment(),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        ) for _ in range(2)]
        try:
            output = [process.communicate(timeout=20) for process in processes]
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        self.assertEqual(sorted(p.returncode for p in processes), [0, 1], output)
        history = self.history()
        self.assertEqual(len(history), 1)
        self.assertEqual((history[0]["old_due_on"], history[0]["new_due_on"]), ("2026-10-07", "2026-10-15"))
        self.assertEqual(self.rows("loans", "--active", columns=LOANS)[0]["due_on"], "2026-10-15")
        self.assertEqual(len(self.rows("inventory", columns=INVENTORY)), 3)
        self.check_integrity()

    def test_new_export_restores_current_reports_and_complete_history(self):
        self.run_cli("renew", "strasse-1", "--due", "2026-10-15", "--on", "2026-10-05")
        commands = [*REPORTS, ("renewals",), ("renewals", "--asset", " STRASSE-1 ")]
        expected = {command: self.run_cli(*command).stdout for command in commands}
        original = self.db.read_bytes()
        destination = self.directory / "recovery.zip"
        self.run_cli("export", str(destination))
        self.assertEqual(self.db.read_bytes(), original)
        with zipfile.ZipFile(destination) as archive:
            self.assertTrue({"catalog.csv", "inventory.csv", "loans.csv", "renewals.csv",
                             "library.sqlite3", "RESTORE.txt"}.issubset(archive.namelist()))
            for name, columns in [("catalog.csv", ["asset_id", "name"]), ("inventory.csv", INVENTORY),
                                  ("loans.csv", LOANS), ("renewals.csv", RENEWALS)]:
                reader = csv.DictReader(io.StringIO(archive.read(name).decode("utf-8")))
                self.assertEqual(reader.fieldnames, columns, name)
                records = list(reader)
                if name == "renewals.csv":
                    self.assertEqual(records, self.history())
            restored = self.directory / "restored.sqlite3"
            restored.write_bytes(archive.read("library.sqlite3"))
        for command, output in expected.items():
            with self.subTest(command=command):
                self.assertEqual(self.run_cli(*command, db=restored).stdout, output)
        existing = destination.read_bytes()
        self.run_cli("export", str(destination), success=False)
        self.assertEqual(destination.read_bytes(), existing)
        self.assertEqual(self.db.read_bytes(), original)
        self.check_integrity(restored)

    def test_catalog_preview_survives_renewal_and_duplicate_batch_stays_atomic(self):
        catalog = self.directory / "catalog.csv"
        catalog.write_text("asset_id,name\n SPARE-2 ,Hammer\n", encoding="utf-8")
        preview = self.run_cli("import", str(catalog)).stdout
        token = next(line.removeprefix("Preview token: ") for line in preview.splitlines()
                     if line.startswith("Preview token: "))
        self.run_cli("renew", "strasse-1", "--due", "2026-10-15", "--on", "2026-10-05")
        self.run_cli("import", str(catalog), "--confirm", token)
        self.assertIn("spare-2", [r["asset_id"] for r in self.rows("inventory", columns=INVENTORY)])
        catalog.write_text("asset_id,name\n x ,One\nX,Two\n", encoding="utf-8")
        self.reject_unchanged("import", str(catalog))
        self.reject_unchanged("import", str(catalog), "--confirm", token)
        self.assertEqual(len(self.history()), 1)

    def test_refused_databases_and_missing_database_remain_unchanged(self):
        foreign = self.directory / "foreign.sqlite3"
        with closing(sqlite3.connect(foreign)) as connection, connection:
            connection.execute("CREATE TABLE unrelated(value TEXT)")
            connection.execute("INSERT INTO unrelated VALUES ('preserve')")
        unknown = self.directory / "unknown.sqlite3"
        self.seed(unknown, version=999)
        collision = self.directory / "collision.sqlite3"
        self.seed(collision, version=1, collision=True)
        for path in [foreign, unknown, collision]:
            for command in [("inventory",), ("renewals",),
                            ("renew", "strasse-1", "--due", "2026-10-15", "--on", "2026-10-05")]:
                with self.subTest(database=path.name, command=command):
                    self.reject_unchanged(*command, db=path)
        empty = self.directory / "empty"
        empty.mkdir()
        absent = empty / "absent.sqlite3"
        self.assertEqual(self.history(db=absent), [])
        self.assertEqual(list(empty.iterdir()), [])
        self.run_cli("renew", "missing", "--due", "2026-10-15", "--on", "2026-10-05",
                     db=absent, success=False)
        self.assertEqual(list(empty.iterdir()), [])

    def test_prior_recovery_archive_remains_usable_for_read_and_renewal(self):
        archive_path = self.directory / "old-recovery.zip"
        expected = {command: self.run_cli(*command, baseline=True).stdout for command in REPORTS}
        self.run_cli("export", str(archive_path), baseline=True)
        with zipfile.ZipFile(archive_path) as archive:
            self.assertNotIn("renewals.csv", archive.namelist())
            restored = self.directory / "old-restored.sqlite3"
            restored.write_bytes(archive.read("library.sqlite3"))
        original = restored.read_bytes()
        for command, output in expected.items():
            self.assertEqual(self.run_cli(*command, db=restored).stdout, output)
        self.assertEqual(self.history(db=restored), [])
        self.assertEqual(restored.read_bytes(), original)
        self.run_cli("renew", "strasse-1", "--due", "2026-10-15", "--on", "2026-10-05", db=restored)
        self.assertEqual(len(self.history(db=restored)), 1)
        self.assertEqual(self.rows("loans", "--active", columns=LOANS, db=restored)[0]["loan_id"], "7")
        self.check_integrity(restored)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    arguments = parser.parse_args()
    PROJECT = arguments.project.resolve()
    BASELINE = arguments.baseline.resolve()
    for directory in [PROJECT, BASELINE]:
        if not (directory / "toolshelf/__main__.py").is_file():
            parser.error(f"ToolShelf entrypoint missing under {directory}")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentAcceptance))
    raise SystemExit(0 if result.wasSuccessful() else 1)

