"""Exercise the actual CLI and retain a self-contained local recovery scenario."""

import csv
import hashlib
import io
from pathlib import Path
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    directory = Path(tempfile.mkdtemp(prefix="journey-", dir=ROOT / "evidence"))
    database = directory / "library.sqlite3"
    transcript = directory / "transcript.txt"
    lines = [f"Interpreter: {sys.version}", f"Scenario directory: {directory}"]

    def record(message):
        lines.append(message)
        transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(*arguments, db=database, expected=0, unchanged=False):
        before = db.read_bytes() if db.exists() else None
        command = [sys.executable, "-B", "-m", "toolshelf", "--db", str(db), *arguments]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=15)
        record("$ " + shlex.join(command))
        record(f"exit={result.returncode}\n{result.stdout}{result.stderr}")
        if result.returncode != expected:
            raise AssertionError(f"Expected exit {expected}, got {result.returncode}; see {transcript}")
        if unchanged:
            after = db.read_bytes() if db.exists() else None
            assert after == before, "Request changed saved database bytes or existence"
            record("Verified: database bytes and existence unchanged.")
        return result.stdout

    def preview(path, *, db=database):
        output = run("import", str(path), db=db, unchanged=True)
        return next(line.removeprefix("Preview token: ") for line in output.splitlines()
                    if line.startswith("Preview token: "))

    run("inventory", unchanged=True)
    run("renewals", unchanged=True)
    run("add", " D-001 ", "Cordless drill")
    run("add", "H-001", "Claw hammer")
    run("add", "d-001", "Overwrite attempt", expected=1, unchanged=True)
    run("add", "X-001", " ", expected=1, unchanged=True)

    catalog = directory / "new-tools.csv"
    contents = 'asset_id,name\nS-001,"Scie, précision"\nStraße-2,"Équerre ""atelier"""\n'
    catalog.write_text(contents, encoding="utf-8-sig", newline="")
    token = preview(catalog)
    run("add", "L-001", "Ladder")
    run("import", str(catalog), "--confirm", token, expected=1, unchanged=True)
    token = preview(catalog)
    catalog.write_text(contents.replace("Scie, précision", "Different saw"), encoding="utf-8-sig", newline="")
    run("import", str(catalog), "--confirm", token, expected=1, unchanged=True)
    catalog.write_text(contents, encoding="utf-8-sig", newline="")
    run("import", str(catalog), "--confirm", token)
    run("add", " STRASSE-2 ", "Unicode collision", expected=1, unchanged=True)

    invalid = directory / "invalid-batch.csv"
    invalid.write_text("asset_id,name\nnew,Valid but must not import\n A ,First\na,Duplicate\n S-001 ,Existing\nblank, \nextra,Two,Three\n", encoding="utf-8")
    for confirm in ((), ("--confirm", "0" * 64)):
        run("import", str(invalid), *confirm, expected=1, unchanged=True)
    assert "new\t" not in run("inventory", unchanged=True)

    run("lend", " D-001 ", "Alex María", "--due", "2026-10-06", "--on", "2026-10-01")
    run("lend", "d-001", "Sam", "--due", "2026-10-07", "--on", "2026-10-02", expected=1, unchanged=True)
    run("lend", "unknown", "Sam", "--due", "2026-10-07", "--on", "2026-10-02", expected=1, unchanged=True)
    run("lend", "h-001", "Sam", "--due", "2026-02-30", "--on", "2026-10-02", expected=1, unchanged=True)
    run("return", "D-001", "--on", "2026-09-30", expected=1, unchanged=True)
    run("overdue", expected=2, unchanged=True)
    due_today = run("overdue", "--as-of", "2026-10-06", unchanged=True)
    assert len(due_today.splitlines()) == 1
    overdue = run("overdue", "--as-of", "2026-10-07", unchanged=True)
    assert "Alex María" in overdue
    run("renew", "D-001", "--due", "2026-10-10", expected=2, unchanged=True)
    run("renew", "D-001", "--due", "2026-10-06", "--on", "2026-10-06", expected=1, unchanged=True)
    run("renew", "\t D-001 \n", "--due", "2026-10-10", "--on", "2026-10-07")
    run("renew", "D-001", "--due", "2026-10-10", "--on", "2026-10-07", expected=1, unchanged=True)
    run("renew", "D-001", "--due", "2026-10-12", "--on", "2026-10-08")
    run("return", "D-001", "--on", "2026-10-07", expected=1, unchanged=True)
    assert len(run("overdue", "--as-of", "2026-10-12", unchanged=True).splitlines()) == 1
    assert "Alex María" in run("overdue", "--as-of", "2026-10-13", unchanged=True)
    run("return", " D-001 ", "--on", "2026-10-08")
    run("return", "d-001", "--on", "2026-10-08", expected=1, unchanged=True)
    run("lend", "D-001", "Sam", "--due", "2026-10-10", "--on", "2026-10-09")
    run("renew", "d-001", "--due", "2026-10-11", "--on", "2026-10-09")
    run("lend", " s-001 ", "Robin", "--due", "2026-10-09", "--on", "2026-10-08")
    run("inventory", "--available", unchanged=True)
    history_output = run("loans", unchanged=True)
    assert len(history_output.splitlines()) == 4
    run("loans", "--active", unchanged=True)
    renewal_output = run("renewals", "--asset", " D-001 ", unchanged=True)
    assert [row["loan_id"] for row in csv.DictReader(io.StringIO(renewal_output), delimiter="\t")] == ["1", "1", "2"]
    late_output = run("overdue", "--as-of", "2026-10-12", unchanged=True)
    assert [row["loan_id"] for row in csv.DictReader(io.StringIO(late_output), delimiter="\t")] == ["3", "2"]

    archive_path = directory / "recovery.zip"
    run("export", str(archive_path), unchanged=True)
    archive_bytes = archive_path.read_bytes()
    run("export", str(archive_path), expected=1, unchanged=True)
    assert archive_path.read_bytes() == archive_bytes
    record("Verified: refusing a repeated export preserved the archive bytes.")

    restored = directory / "restored.sqlite3"
    catalog_copy = directory / "exported-catalog.csv"
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        expected_files = {"catalog.csv", "inventory.csv", "loans.csv", "renewals.csv", "library.sqlite3", "RESTORE.txt"}
        assert set(archive.namelist()) == expected_files
        restored.write_bytes(archive.read("library.sqlite3"))
        catalog_copy.write_bytes(archive.read("catalog.csv"))
        inventory_rows = list(csv.DictReader(io.StringIO(archive.read("inventory.csv").decode("utf-8"))))
        loan_rows = list(csv.DictReader(io.StringIO(archive.read("loans.csv").decode("utf-8"))))
        renewal_rows = list(csv.DictReader(io.StringIO(archive.read("renewals.csv").decode("utf-8"))))
        assert len(inventory_rows) == 5 and len(loan_rows) == 3
        assert [row["renewal_id"] for row in renewal_rows] == ["1", "2", "3"]
        record("Archive contents: " + ", ".join(sorted(expected_files)))
        record("Verified: archive has 5 tools, 3 loans (1 closed, 2 active) and 3 renewal events.")

    for arguments in (("inventory",), ("loans",), ("loans", "--active"), ("renewals",),
                      ("renewals", "--asset", " D-001 "), ("overdue", "--as-of", "2026-10-12")):
        actual = run(*arguments, db=restored, unchanged=True)
        expected = run(*arguments, unchanged=True)
        assert actual == expected
    connection = sqlite3.connect(restored.as_uri() + "?mode=ro", uri=True)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()
    record("Verified: restored CLI output matches live inventory, loans, renewals and overdue; SQLite integrity and foreign keys pass.")
    run("renew", "D-001", "--due", "2026-10-13", "--on", "2026-10-10", db=restored)
    recovered_events = list(csv.DictReader(io.StringIO(run("renewals", db=restored, unchanged=True)), delimiter="\t"))
    assert [row["renewal_id"] for row in recovered_events] == ["1", "2", "3", "4"]
    assert recovered_events[-1]["loan_id"] == "2" and recovered_events[-1]["old_due_on"] == "2026-10-11"
    record("Verified: recovered database accepts a new renewal without reusing event IDs or changing its loan ID.")

    copied = directory / "catalog-copy.sqlite3"
    copy_token = preview(catalog_copy, db=copied)
    run("import", str(catalog_copy), "--confirm", copy_token, db=copied)
    output = run("inventory", db=copied, unchanged=True)
    copied_rows = list(csv.DictReader(io.StringIO(output), delimiter="\t"))
    assert [(r["asset_id"], r["name"]) for r in copied_rows] == [(r["asset_id"], r["name"]) for r in inventory_rows]
    record("Verified: exported catalog imported into a new database with every ID and quoted Unicode name preserved.")
    record(f"Recovery archive SHA-256: {hashlib.sha256(archive_bytes).hexdigest()}")
    record("RESULT: PASS — full journey, expected failures, recovery and transfer assertions passed.")
    print(f"PASS: {transcript.relative_to(ROOT)}")
    print(f"Recovery archive: {archive_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
