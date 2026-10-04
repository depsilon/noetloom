"""Transactional SQLite storage with explicit database ownership."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3

from .domain import ToolShelfError, asset_identity, calendar_date, clean_text
from .files import new_file


APPLICATION_ID = 0x54534846  # TSHF
SCHEMA_VERSION = 2
SCHEMA = (
    """CREATE TABLE tools (
        asset_id TEXT PRIMARY KEY NOT NULL CHECK(length(trim(asset_id)) > 0),
        name TEXT NOT NULL CHECK(length(trim(name)) > 0)
    )""",
    """CREATE TABLE loans (
        loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id TEXT NOT NULL REFERENCES tools(asset_id),
        borrower TEXT NOT NULL CHECK(length(trim(borrower)) > 0),
        lent_on TEXT NOT NULL,
        due_on TEXT NOT NULL CHECK(due_on >= lent_on),
        returned_on TEXT CHECK(returned_on IS NULL OR returned_on >= lent_on)
    )""",
    "CREATE UNIQUE INDEX one_active_loan ON loans(asset_id) WHERE returned_on IS NULL",
)


def initialize(connection: sqlite3.Connection) -> None:
    for statement in SCHEMA:
        connection.execute(statement)
    connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def check_database(connection: sqlite3.Connection, *, allow_initialize: bool) -> int:
    application_id = connection.execute("PRAGMA application_id").fetchone()[0]
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if allow_initialize and application_id == 0 and version == 0:
        objects = connection.execute(
            "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()
        if not objects:
            initialize(connection)
            return SCHEMA_VERSION
    if application_id != APPLICATION_ID:
        raise ToolShelfError("This file is not a ToolShelf database; choose another --db path.")
    if version not in (1, SCHEMA_VERSION):
        raise ToolShelfError(
            f"Unsupported ToolShelf database version {version}; this program supports {SCHEMA_VERSION}."
        )
    return version


def normalize_legacy_database(connection: sqlite3.Connection) -> None:
    """Upgrade an owned v1 database inside the caller's transaction."""
    replacements = []
    originals = {}
    for row in connection.execute("SELECT asset_id FROM tools ORDER BY asset_id"):
        original = row[0]
        normalized = asset_identity(original)
        if normalized in originals:
            raise ToolShelfError(
                f"Legacy asset IDs {originals[normalized]!r} and {original!r} collide "
                "after normalization. Resolve those IDs in a backup before retrying; "
                "the database was not changed."
            )
        originals[normalized] = original
        if original != normalized:
            replacements.append((original, normalized))
    connection.execute("PRAGMA defer_foreign_keys = ON")
    for original, normalized in replacements:
        connection.execute("UPDATE tools SET asset_id = ? WHERE asset_id = ?", (normalized, original))
        connection.execute("UPDATE loans SET asset_id = ? WHERE asset_id = ?", (normalized, original))
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def check_parent(self) -> None:
        if not self.path.parent.is_dir():
            raise ToolShelfError(f"Database parent directory does not exist: {self.path.parent}")

    @contextmanager
    def read(self):
        self.check_parent()
        if self.path.exists() or self.path.is_symlink():
            uri = self.path.resolve().as_uri() + "?mode=ro"
            connection = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=5)
        else:
            connection = sqlite3.connect(":memory:", isolation_level=None)
            initialize(connection)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN")
            version = check_database(connection, allow_initialize=False)
            if version == 1:
                # Reads expose canonical IDs without migrating the user's file.
                snapshot = sqlite3.connect(":memory:", isolation_level=None)
                try:
                    connection.backup(snapshot)
                except BaseException:
                    snapshot.close()
                    raise
                connection.close()
                connection = snapshot
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute("BEGIN")
                normalize_legacy_database(connection)
                connection.commit()
                connection.execute("BEGIN")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def write(self):
        self.check_parent()
        exists = self.path.exists() or self.path.is_symlink()
        if exists:
            uri = self.path.resolve().as_uri() + "?mode=rw"
            connection = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=5)
        else:
            # A failed first mutation must not leave even an empty database.
            connection = sqlite3.connect(":memory:", isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            version = check_database(connection, allow_initialize=True)
            if version == 1:
                normalize_legacy_database(connection)
            yield connection
            connection.commit()
            if not exists:
                with new_file(self.path) as temporary:
                    destination = sqlite3.connect(temporary)
                    try:
                        connection.backup(destination)
                    finally:
                        destination.close()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def add(self, asset_id: str, name: str) -> None:
        asset_id = asset_identity(asset_id)
        name = clean_text(name, "Tool name")
        with self.write() as connection:
            if connection.execute("SELECT 1 FROM tools WHERE asset_id = ?", (asset_id,)).fetchone():
                raise ToolShelfError(f"Asset ID {asset_id!r} already exists.")
            connection.execute("INSERT INTO tools(asset_id, name) VALUES (?, ?)", (asset_id, name))

    def inventory(self, *, available_only: bool = False) -> list[dict]:
        query = """SELECT t.asset_id, t.name,
            CASE WHEN l.loan_id IS NULL THEN 'available' ELSE 'loaned' END AS status,
            coalesce(l.borrower, '') AS borrower, coalesce(l.due_on, '') AS due_on
            FROM tools t LEFT JOIN loans l
            ON t.asset_id = l.asset_id AND l.returned_on IS NULL"""
        if available_only:
            query += " WHERE l.loan_id IS NULL"
        query += " ORDER BY t.asset_id"
        with self.read() as connection:
            return [dict(row) for row in connection.execute(query)]

    @staticmethod
    def require_tool(connection: sqlite3.Connection, asset_id: str) -> None:
        if not connection.execute("SELECT 1 FROM tools WHERE asset_id = ?", (asset_id,)).fetchone():
            raise ToolShelfError(f"Unknown asset ID {asset_id!r}.")

    def lend(self, asset_id: str, borrower: str, due_on: str, lent_on: str) -> int:
        asset_id = asset_identity(asset_id)
        borrower = clean_text(borrower, "Borrower")
        due_on = calendar_date(due_on, "Due date")
        lent_on = calendar_date(lent_on, "Lending date")
        if due_on < lent_on:
            raise ToolShelfError("Due date cannot precede lending date.")
        with self.write() as connection:
            self.require_tool(connection, asset_id)
            if connection.execute(
                "SELECT 1 FROM loans WHERE asset_id = ? AND returned_on IS NULL", (asset_id,)
            ).fetchone():
                raise ToolShelfError(f"Asset {asset_id!r} is already loaned.")
            cursor = connection.execute(
                "INSERT INTO loans(asset_id, borrower, lent_on, due_on) VALUES (?, ?, ?, ?)",
                (asset_id, borrower, lent_on, due_on),
            )
            return cursor.lastrowid

    def return_tool(self, asset_id: str, returned_on: str) -> int:
        asset_id = asset_identity(asset_id)
        returned_on = calendar_date(returned_on, "Return date")
        with self.write() as connection:
            self.require_tool(connection, asset_id)
            loan = connection.execute(
                "SELECT loan_id, lent_on FROM loans WHERE asset_id = ? AND returned_on IS NULL",
                (asset_id,),
            ).fetchone()
            if loan is None:
                raise ToolShelfError(f"Asset {asset_id!r} has no active loan.")
            if returned_on < loan["lent_on"]:
                raise ToolShelfError("Return date cannot precede lending date.")
            connection.execute(
                "UPDATE loans SET returned_on = ? WHERE loan_id = ?", (returned_on, loan["loan_id"])
            )
            return loan["loan_id"]

    def loans(self, *, active_only: bool = False, as_of: str | None = None) -> list[dict]:
        query = """SELECT l.loan_id, l.asset_id, t.name, l.borrower,
            l.lent_on, l.due_on, coalesce(l.returned_on, '') AS returned_on
            FROM loans l JOIN tools t ON l.asset_id = t.asset_id"""
        parameters = ()
        if as_of is not None:
            as_of = calendar_date(as_of, "As-of date")
            query += " WHERE l.returned_on IS NULL AND l.lent_on <= ? AND l.due_on < ?"
            parameters = (as_of, as_of)
            query += " ORDER BY l.due_on, l.loan_id"
        else:
            if active_only:
                query += " WHERE l.returned_on IS NULL"
            query += " ORDER BY l.loan_id"
        with self.read() as connection:
            return [dict(row) for row in connection.execute(query, parameters)]
