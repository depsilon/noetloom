"""Whole-batch catalog import and consistent local recovery archives."""

import csv
from dataclasses import dataclass
import hashlib
import hmac
import io
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import zipfile

from .domain import ToolShelfError, asset_identity, clean_text
from .files import new_file
from .storage import Store


CATALOG_COLUMNS = ("asset_id", "name")
INVENTORY_COLUMNS = ("asset_id", "name", "status", "borrower", "due_on")
LOAN_COLUMNS = ("loan_id", "asset_id", "name", "borrower", "lent_on", "due_on", "returned_on")
RENEWAL_COLUMNS = ("renewal_id", "loan_id", "asset_id", "old_due_on", "new_due_on", "renewed_on")


@dataclass(frozen=True)
class CatalogRow:
    line: int
    asset_id: str | None
    name: str | None


@dataclass(frozen=True)
class CatalogBatch:
    contents: bytes
    rows: tuple[CatalogRow, ...]
    errors: tuple[str, ...]


def read_catalog(path: str | Path) -> CatalogBatch:
    contents = Path(path).read_bytes()
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ToolShelfError("CSV must be UTF-8 text (an optional UTF-8 BOM is accepted).") from None
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader, None)
    except csv.Error as error:
        raise ToolShelfError(f"CSV line 1: malformed header: {error}") from None
    if header != list(CATALOG_COLUMNS):
        raise ToolShelfError("CSV line 1: headers must be exactly asset_id,name in that order.")
    rows = []
    errors = []
    seen = {}
    while True:
        line = reader.line_num + 1
        try:
            values = next(reader)
        except StopIteration:
            break
        except csv.Error as error:
            errors.append(f"Line {line}: malformed CSV: {error}")
            break  # The parser cannot reliably find another record after broken quoting.
        if len(values) != 2:
            errors.append(f"Line {line}: expected 2 fields, found {len(values)}.")
            continue
        asset_id = name = None
        try:
            asset_id = asset_identity(values[0])
        except ToolShelfError as error:
            errors.append(f"Line {line}: {error}")
        try:
            name = clean_text(values[1], "Tool name")
        except ToolShelfError as error:
            errors.append(f"Line {line}: {error}")
        if asset_id is not None:
            if asset_id in seen:
                errors.append(f"Line {line}: asset ID {asset_id!r} duplicates line {seen[asset_id]} after normalization.")
            else:
                seen[asset_id] = line
        rows.append(CatalogRow(line, asset_id, name))
    if not rows and not errors:
        errors.append("CSV contains no catalog rows.")
    return CatalogBatch(contents, tuple(rows), tuple(errors))


def catalog_rows(connection: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in connection.execute("SELECT asset_id, name FROM tools ORDER BY asset_id")]


def validate_batch(batch: CatalogBatch, catalog: list[dict]) -> None:
    errors = list(batch.errors)
    existing = {row["asset_id"] for row in catalog}
    for row in batch.rows:
        if row.asset_id in existing:
            errors.append(f"Line {row.line}: asset ID {row.asset_id!r} already exists in the catalog.")
    if errors:
        raise ToolShelfError("CSV import rejected:\n" + "\n".join(errors))


def preview_token(batch: CatalogBatch, catalog: list[dict]) -> str:
    catalog_bytes = json.dumps(catalog, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    binding = b"ToolShelf catalog preview v1\0" + hashlib.sha256(batch.contents).digest()
    binding += hashlib.sha256(catalog_bytes).digest()
    return hashlib.sha256(binding).hexdigest()


def preview_import(store: Store, path: str | Path) -> tuple[CatalogBatch, str]:
    batch = read_catalog(path)
    with store.read() as connection:
        catalog = catalog_rows(connection)
        validate_batch(batch, catalog)
        token = preview_token(batch, catalog)
    return batch, token


def apply_import(store: Store, path: str | Path, token: str) -> int:
    if not re.fullmatch(r"[0-9a-f]{64}", token):
        raise ToolShelfError("Invalid preview token; preview this CSV without --confirm first.")
    batch = read_catalog(path)
    with store.write() as connection:
        catalog = catalog_rows(connection)
        validate_batch(batch, catalog)
        if not hmac.compare_digest(preview_token(batch, catalog), token):
            raise ToolShelfError("Preview is stale; preview this CSV again without --confirm.")
        connection.executemany(
            "INSERT INTO tools(asset_id, name) VALUES (?, ?)",
            [(row.asset_id, row.name) for row in batch.rows],
        )
    return len(batch.rows)


def csv_text(rows: list[dict], columns: tuple[str, ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


RESTORE_TEXT = """ToolShelf local recovery archive

library.sqlite3 is the complete database snapshot, including active and closed loans
and every renewal event with its original ID.
Extract it to an existing directory under a NEW filename, for example restored.sqlite3.
From the ToolShelf application directory, inspect it with Python 3.11+:
  python3.13 -B -m toolshelf --db /path/to/restored.sqlite3 inventory
  python3.13 -B -m toolshelf --db /path/to/restored.sqlite3 loans
  python3.13 -B -m toolshelf --db /path/to/restored.sqlite3 renewals
Use that --db path for subsequent work. Preserve the original database until satisfied.

catalog.csv has the exact asset_id,name headers accepted by the catalog import command.
inventory.csv includes current availability, active borrower and due date.
loans.csv includes every active and closed loan; blank returned_on means active.
renewals.csv includes renewal_id,loan_id,asset_id,old_due_on,new_due_on,renewed_on
in renewal-ID order. Loan due dates are current; events retain earlier due dates.
All CSV files are UTF-8 and preserve raw text, including formula-looking values.
Do not treat them as spreadsheet-sanitized data. Catalog import does not restore loans;
use library.sqlite3 for full recovery. Dates are YYYY-MM-DD. IDs are trimmed/casefolded.
The archive contains borrower names. Keep it in a suitably private local directory.
"""


def export_archive(store: Store, destination: str | Path) -> None:
    destination = Path(destination)
    if destination.resolve() == store.path.resolve() and not destination.exists():
        raise ToolShelfError("Export destination must differ from the database path.")
    with new_file(destination) as archive_path:
        with tempfile.TemporaryDirectory(prefix=".toolshelf-export-", dir=destination.parent) as directory:
            snapshot_path = Path(directory) / "library.sqlite3"
            snapshot = sqlite3.connect(snapshot_path)
            try:
                with store.read() as source:
                    source.backup(snapshot)
            finally:
                snapshot.close()
            # Every representation comes from the same immutable backup, even if a
            # volunteer changes the live library while the archive is being built.
            saved = Store(snapshot_path)
            with saved.read() as connection:
                catalog = catalog_rows(connection)
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("catalog.csv", csv_text(catalog, CATALOG_COLUMNS))
                archive.writestr("inventory.csv", csv_text(saved.inventory(), INVENTORY_COLUMNS))
                archive.writestr("loans.csv", csv_text(saved.loans(), LOAN_COLUMNS))
                archive.writestr("renewals.csv", csv_text(saved.renewals(), RENEWAL_COLUMNS))
                archive.write(snapshot_path, "library.sqlite3")
                archive.writestr("RESTORE.txt", RESTORE_TEXT)
