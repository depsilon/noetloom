# ToolShelf implementation guidance

Applies to CLI, persistence, lending and transfer work. Read the phase in PLAN.md first.
Use only Python 3.11+ and its standard library. Keep CLI parsing/presentation apart from
domain validation and storage; favor direct functions over a framework.

## Data and CLI contracts

- `tools(asset_id, name)` retains stable canonical IDs: trim whitespace and apply Unicode
  `casefold()` at every ID boundary. Trim surrounding whitespace before checking the
  remaining ID for internal control characters. All lookups, lending, returns and CSV duplicate checks
  must use that same identity function. Preserve printed names and borrowers. `loans` retains a stable integer
  loan ID, asset ID, borrower, lending date, due date and nullable return date.
- A foreign key requires every loan's tool. A partial unique index permits at most one
  loan with no return date per tool. Application validation gives helpful messages;
  database constraints are a second defense. Enable foreign keys on every connection.
- Dates use strict `YYYY-MM-DD` syntax and real calendar dates. Normalize text at the
  input boundary; reject blanks and control characters. Preserve printable Unicode.
- Persist only after all request validation. Use explicit transactions and `BEGIN IMMEDIATE`
  for mutations. Never use `executescript` inside an atomic mutation: it commits implicitly.
- Identify owned databases by SQLite application ID and schema version. Reject foreign or
  unsupported databases. Opening a read command or CSV preview must not create a disk DB.
- Version 2 stores normalized IDs. Read version-1 data through a normalized in-memory
  snapshot; migrate it on a successful write in the same transaction as the request.
  Preflight all normalization collisions and preserve loan references. A failed request
  must roll the migration back as well as the request.
- Build the first successful write in memory and publish a complete SQLite file exclusively.
  This prevents failed first requests from leaving an empty file. Publication and exports
  use a temporary file in the destination directory and an exclusive hard link; a competing
  creator receives a retry error. The filesystem must support that operation.
- Domain failures produce a short message on stderr and a nonzero status, with no traceback.
  Unexpected programming errors should still be visible during development.
- Use stable tab-separated command tables with headers, and clear mutation confirmations.
  `--db` selects a file; its parent must already exist. The default is `toolshelf.sqlite3`
  in the working directory. Documentation must show explicit DB selection for examples.

## Lending and query rules

Lend only a known available asset to a nonempty borrower. Require due date >= lending date.
Return only an active loan with return date >= lending date. Keep closed loans; lending
again creates a new loan ID. Inventory and active-loan queries reflect current state.
Overdue requires `--as-of`; list currently active loans whose lending date <= that date
and due date < that date. It is not a historical reconstruction of returned loans.
Order catalog by asset ID, loan history by loan ID, and overdue by due date then loan ID.

## Import and export rules

Parse CSV strictly as UTF-8 with an optional BOM. Require precisely `asset_id,name` headers.
Reject malformed CSV, missing/extra fields, invalid cells, and duplicate normalized IDs
(including case/whitespace variants within the batch and against saved catalog rows). Report physical
line numbers and every recoverable row error. Never apply the valid subset of an invalid batch.
Preview prints prospective additions and a token. A second command explicitly supplies that
token; recheck under a write transaction so intervening catalog changes cannot bypass it.
Do not mutate catalog data for a preview, stale token, or invalid input.

Export one consistent snapshot, including all tools and both active and closed loans.
Write CSV with the standard `csv` module and stable headers. Include a database snapshot
and recovery instructions. Publish the archive only after all content is complete and
refuse existing destinations. Clean temporary files on failure. CSV preserves raw text
for round-trip transfer; it is not a spreadsheet formula-sanitization format.
Include `catalog.csv` with import-compatible headers in addition to `inventory.csv`,
`loans.csv`, `library.sqlite3` and `RESTORE.txt`. Export must not create a ZIP at an absent
database's own path. All archive representations must come from the same completed backup.

## Checks and review

Use `unittest` and `tempfile`, with no mocks of SQLite for persistence tests. Check actual
subprocess invocation, return codes, stdout/stderr, restart persistence and stored state.
Tests should target behavior and safety, especially no-write failures, concurrent double
lending, stale CSV previews, malformed batches, and export recovery. Do not merely test
private implementation structure. Keep scenario artifacts under `evidence/` when useful;
temporary test databases must not become the default user database.

At each phase inspect outputs and errors, repair failures, record exact commands and results,
then continue. At completion run the entire test suite, a representative CLI journey with
real files, recovery from the exported snapshot, and an adversarial review of state integrity,
atomicity and documented contracts. Record limitations without implying unrun checks passed.
