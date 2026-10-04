# ToolShelf

A local, offline command-line tool library. Python 3.11+ and its standard library are
the only requirements; no installation or service is needed. On this machine use
`python3.13` because `python3` is Python 3.9.6. Elsewhere substitute a Python 3.11+
interpreter. Run commands from this directory.

Choose a database with `--db` **before** the command. Its parent directory must already
exist. The default is `toolshelf.sqlite3` in the current working directory. The first
successful write creates it; queries, previews and failed first writes do not.

## Catalog and lending

The following example uses explicit dates so its results stay reproducible:

```sh
python3.13 -B -m toolshelf --db library.sqlite3 add D-001 "Cordless drill"
python3.13 -B -m toolshelf --db library.sqlite3 add H-001 "Claw hammer"
python3.13 -B -m toolshelf --db library.sqlite3 inventory
python3.13 -B -m toolshelf --db library.sqlite3 lend " d-001 " "Alex María" --due 2026-10-06 --on 2026-10-01
python3.13 -B -m toolshelf --db library.sqlite3 inventory --available
python3.13 -B -m toolshelf --db library.sqlite3 overdue --as-of 2026-10-06
python3.13 -B -m toolshelf --db library.sqlite3 overdue --as-of 2026-10-07
python3.13 -B -m toolshelf --db library.sqlite3 return D-001 --on 2026-10-07
python3.13 -B -m toolshelf --db library.sqlite3 lend D-001 Sam --due 2026-10-10 --on 2026-10-08
python3.13 -B -m toolshelf --db library.sqlite3 loans
python3.13 -B -m toolshelf --db library.sqlite3 loans --active
```

IDs are unique after trimming whitespace and Unicode `casefold()`: `D-001`, `d-001`
and ` D-001 ` identify the same tool. `Straße` and `STRASSE` also collide. Stored and
printed IDs use the canonical form; tool and borrower names preserve their letter case.
IDs first discard surrounding whitespace, including tabs and newlines; the remaining ID
must be nonempty, single-line, and free of controls. Names and borrowers reject controls
and trim surrounding spaces.
Duplicate IDs never replace a tool.

Lending requires an available, known tool, a borrower, and a real `YYYY-MM-DD` due date
on or after the lending date. Returning closes the active loan and preserves its history;
a later loan receives a new ID. Return dates cannot precede their lending dates.
If omitted, `--on` uses today's local calendar date. Due and lending dates may be equal.

`overdue` always requires `--as-of`. A tool due on that date is **not overdue** until
the following day. Results include only currently active loans lent on or before the
query date. This command does not reconstruct historical inventory or previously returned
loans. Inventory reflects current availability, including loans with an explicit future date.

## Preview and import a catalog

Create a UTF-8 file named `new-tools.csv` with exactly these two headers, in this order:

```csv
asset_id,name
S-001,"Scie, précision"
Straße-2,"Équerre ""atelier"""
```

Preview without writing:

```sh
python3.13 -B -m toolshelf --db library.sqlite3 import new-tools.csv
```

Inspect the prospective rows, then copy the printed 64-character `Preview token` into
the following command in place of `TOKEN`:

```sh
python3.13 -B -m toolshelf --db library.sqlite3 import new-tools.csv --confirm TOKEN
```

The token binds the exact file bytes and the current catalog. Any change to either
requires another preview. Loan-only changes do not invalidate a catalog preview.
Confirmation rechecks everything under the database write lock. It cannot apply part
of a batch or silently update existing tools.

An optional UTF-8 BOM is accepted. Extra or missing fields, empty batches, invalid
cells, and IDs that collide within the batch or with existing IDs are rejected. Errors
identify physical starting line numbers and include all recoverable row errors; broken
CSV quoting stops parsing when no safe next record boundary exists. No rows are written
from a rejected batch. Quoted Unicode, commas and quotes are preserved in valid names.

## Export and recover

```sh
python3.13 -B -m toolshelf --db library.sqlite3 export library-backup.zip
```

Choose a new archive filename each time. ToolShelf refuses existing files, directories
and symlinks. It publishes the ZIP only after every file is complete and cleans temporary
files if export fails. The original database is unchanged.

| Archive file | Contents |
| --- | --- |
| `catalog.csv` | `asset_id,name`, suitable for preview/import into an empty or disjoint catalog |
| `inventory.csv` | Tools, current availability, active borrower and due date |
| `loans.csv` | All loan IDs, tools, borrowers, lending/due dates and nullable return dates |
| `library.sqlite3` | Complete, restorable database snapshot |
| `RESTORE.txt` | Recovery and format instructions |

Every file comes from the same snapshot, including when another local process is
lending or returning tools. CSV files preserve raw text, including formula-looking
names; they are not a spreadsheet sanitization format. Catalog import does not restore
loan history. Use the SQLite snapshot for complete recovery.

Extract `library.sqlite3` from the archive into a **new** file such as
`restored.sqlite3`, preserving the live database. Then inspect and use it:

```sh
python3.13 -B -m toolshelf --db restored.sqlite3 inventory
python3.13 -B -m toolshelf --db restored.sqlite3 loans
```

Keep using that `--db` path to operate the restored library. Databases and exports
contain borrower names; the local filesystem controls who can access them.

## Errors and existing databases

Tables are tab-separated with headers. Catalog is ordered by ID; history by loan ID;
overdue by due date then loan ID. Domain and local file errors go to stderr and return
status 1. Missing or incorrect command arguments return status 2. Invalid requests
leave saved data unchanged. Separate processes share SQLite's write lock; only one can
lend an available tool. If two processes first create the same database path concurrently,
one may receive an existing-destination error and should retry its command.

The app identifies its own databases and rejects foreign or unsupported versions.
For the original version-1 catalog, reads show canonical IDs without changing the file.
The next successful write upgrades IDs and loan references to version 2 atomically.
If older tools collide after normalization, every command refuses the ambiguous catalog
without modifying it. Preserve a backup and explicitly repair those identities before
retrying; the app provides no deletion or renaming command.

```sh
python3.13 -B -m toolshelf --help
python3.13 -B -m toolshelf import --help
```

## Development and verification

Start with [START-HERE.md](START-HERE.md). The local delivery evidence and execution limits
are recorded in [VALIDATION.md](VALIDATION.md).

```sh
python3.13 -B -m unittest discover -s tests -v
python3.13 -B -m compileall -q toolshelf tests
python3.13 -B scripts/verify_journey.py
```

Tests use temporary files beneath `evidence/` and real SQLite databases and CLI processes.
The journey command retains a new scenario directory, transcript, archive and restored
database under `evidence/`; it does not touch your library database. No third-party
packages, network access, model APIs, dashboards, authentication, cloud sync or notifications
are part of this application.
