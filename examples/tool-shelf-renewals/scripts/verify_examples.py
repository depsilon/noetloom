"""Run README CLI examples and restore the retained pre-renewal recovery archives."""

from contextlib import closing
import csv
from datetime import date, timedelta
import hashlib
import io
from pathlib import Path
import re
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = Path(tempfile.mkdtemp(prefix="renewal-examples-", dir=ROOT / "evidence"))
    transcript = directory / "transcript.txt"
    lines = [f"Interpreter: {sys.version}", "README and prior-recovery acceptance examples"]

    def record(text):
        lines.append(text)
        transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(arguments):
        command = [sys.executable, "-B", "-m", "toolshelf", *arguments]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=15)
        record("$ " + shlex.join(command))
        record(f"exit={result.returncode}\n{result.stdout}{result.stderr}")
        assert result.returncode == 0, f"CLI example failed; see {transcript}"
        return result.stdout

    # Execute the README's actual CLI lines, replacing only local example paths
    # and the token it instructs the volunteer to copy from their preview.
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    csv_example = re.search(r"```csv\n(.*?)```", readme, flags=re.DOTALL).group(1)
    (directory / "new-tools.csv").write_text(csv_example, encoding="utf-8")
    token = None
    count = 0
    paths = {name: str(directory / name) for name in (
        "library.sqlite3", "restored.sqlite3", "new-tools.csv", "library-backup.zip",
    )}
    restored = directory / "restored.sqlite3"
    for block in re.findall(r"```sh\n(.*?)```", readme, flags=re.DOTALL):
        for line in block.splitlines():
            if not line.startswith("python3.13 -B -m toolshelf "):
                continue
            arguments = shlex.split(line)[4:]
            if "restored.sqlite3" in arguments and not restored.exists():
                with zipfile.ZipFile(directory / "library-backup.zip") as archive:
                    with restored.open("xb") as output:
                        output.write(archive.read("library.sqlite3"))
                record("Extracted library.sqlite3 to a new restored.sqlite3 as instructed.")
            arguments = [paths.get(value, value) for value in arguments]
            if "TOKEN" in arguments:
                assert token is not None, "README confirmation precedes its preview"
                arguments[arguments.index("TOKEN")] = token
            output = run(arguments)
            for output_line in output.splitlines():
                if output_line.startswith("Preview token: "):
                    token = output_line.removeprefix("Preview token: ")
            count += 1
    for arguments in (("inventory",), ("loans",), ("renewals",)):
        assert run(["--db", paths["library.sqlite3"], *arguments]) == run(["--db", str(restored), *arguments])
    record(f"PASS: all {count} README CLI examples and restored-query comparisons.")

    # Read the actual previous archives supplied with this application. Do not
    # regenerate them using the new exporter or modify their historical artifacts.
    legacy_count = 0
    for archive_path in sorted((ROOT / "evidence").glob("journey-*/recovery.zip")):
        original = archive_path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            if "renewals.csv" in archive.namelist():
                continue
            recovered = directory / f"prior-recovery-{legacy_count + 1}.sqlite3"
            with recovered.open("xb") as output:
                output.write(archive.read("library.sqlite3"))
            expected_inventory = list(csv.DictReader(io.StringIO(archive.read("inventory.csv").decode("utf-8"))))
            expected_loans = list(csv.DictReader(io.StringIO(archive.read("loans.csv").decode("utf-8"))))
        record(f"Prior archive: {archive_path.relative_to(ROOT)}; SHA-256 {hashlib.sha256(original).hexdigest()}")
        before = recovered.read_bytes()
        for command, expected in (("inventory", expected_inventory), ("loans", expected_loans), ("renewals", [])):
            actual = run(["--db", str(recovered), command])
            assert list(csv.DictReader(io.StringIO(actual), delimiter="\t")) == expected
            assert recovered.read_bytes() == before
        with closing(sqlite3.connect(recovered.as_uri() + "?mode=ro", uri=True)) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            assert version in (1, 2), version
        active = next(row for row in expected_loans if row["returned_on"] == "")
        due = (date.fromisoformat(active["due_on"]) + timedelta(days=1)).isoformat()
        run(["--db", str(recovered), "renew", active["asset_id"], "--due", due, "--on", active["lent_on"]])
        history = list(csv.DictReader(io.StringIO(run(["--db", str(recovered), "renewals"])), delimiter="\t"))
        assert history == [{
            "renewal_id": "1", "loan_id": active["loan_id"], "asset_id": active["asset_id"],
            "old_due_on": active["due_on"], "new_due_on": due, "renewed_on": active["lent_on"],
        }]
        with closing(sqlite3.connect(recovered.as_uri() + "?mode=ro", uri=True)) as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert archive_path.read_bytes() == original
        legacy_count += 1
        record(f"PASS: prior version-{version} recovery preserves queries/bytes, then renews its original loan on upgrade.")
    assert legacy_count > 0, "No previous recovery examples were found"
    record(f"RESULT: PASS — {count} README CLI examples and {legacy_count} prior recovery archives.")
    print(f"PASS: {transcript.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
