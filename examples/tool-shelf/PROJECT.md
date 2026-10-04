# ToolShelf project owner

## Objective and completion

A neighborhood tool-library volunteer needs a small, reliable local command-line tool
to catalog assets, lend them, accept returns, and find overdue loans. Deliver a functioning
Python 3.11+ standard-library application, meaningful automated tests, clear usage, and
actual full-journey and failure-path evidence. A fresh developer must be able to resume
from ordinary Markdown here without the original conversation.

Observable obligations:

- Asset IDs uniquely identify named tools across process restarts.
- Inventory shows availability and can select only available tools.
- A named borrower and valid due date are required to lend an available asset.
- A return closes one active loan and retains its history. Double loans, unknown assets,
  duplicate IDs, repeated returns, and invalid dates fail without changing saved state.
- Overdue is evaluated against a required explicit date, with due dates exclusive:
  a loan due on the query date is not overdue that day.
- CSV catalog import previews the entire batch, reports row errors, and requires an
  unchanged confirmed preview before committing. An invalid batch writes no catalog rows.
- Inventory and loan history can be exported as useful transfer files, with a complete
  local database snapshot for recovery. Existing export files are never overwritten.
- CLI errors are understandable and return nonzero status. The app stays local and offline.

## Constraints, authority and deferred scope

Local file edits and ordinary application/test commands are authorized. No third-party
dependencies, network calls, model APIs, installs, remote publication, deployments,
external services, spending or messaging. No shared dashboards, authentication, cloud
sync, web interfaces or notifications. Those stay deferred unless explicit later steering
changes the scope and grants any needed authority. No commits are necessary for delivery.

## Working decisions and assumptions

- Use `python3 -m toolshelf` from this directory, with a selectable SQLite database.
  SQLite supplies transactions, a uniqueness constraint for active loans and portable backup.
- One local library owns one database. Commands may run in separate processes; SQLite
  serializes writers. Database files and backups contain borrower names and belong to
  the volunteer; filesystem access is the access-control boundary.
- **Accepted correction:** Asset IDs ignore surrounding whitespace and letter case everywhere,
  including storage, lookup, lending/returns and CSV import. Canonical identity uses trimmed
  Unicode `casefold()` text. Trim boundary whitespace, including tabs and newlines, before
  checking the remaining ID for forbidden internal controls. A CSV batch whose IDs
  collide after normalization fails in full.
  Names and borrowers remain trimmed single-line text. Empty values and control characters
  are rejected. No delete/rename or borrower registry is needed. This supersedes the initial
  case-sensitive ID decision; old phase-1 checks alone no longer prove catalog completion.
- Lending and return dates are local calendar dates; `--on` can set them explicitly and
  otherwise uses today's date. Due dates cannot precede lending. Returns cannot precede
  lending. The original brief does not request historical point-in-time inventory.
- CSV import is insert-only with exactly `asset_id,name` headers (UTF-8 with an optional
  BOM). Duplicate IDs within a batch or already in the catalog are errors. No silent updates.
- A preview token binds file bytes and current catalog rows. Applying a changed preview
  requires a new preview; applying acquires the database write lock before final validation.
- Export is a new ZIP archive containing CSV inventory, CSV history and a restorable
  SQLite snapshot. This makes complete recovery possible without inventing a loan import UI.
- Schema version 2 stores canonical IDs. Version-1 reads normalize an in-memory snapshot
  without changing the file; the next successful mutation upgrades IDs and loan references
  atomically. Legacy IDs that collide after normalization fail unchanged and require an
  explicit local data repair from a backup. The app never chooses which tool to discard.
- First writes prepare a complete database before publishing it without replacement.
  If two processes create the same new database path simultaneously, one succeeds and
  the other receives a retry error. Existing database mutations use SQLite's write lock.

No material questions currently block implementation. Routine design decisions may be
revised from evidence within the brief; record consequential changes here and in the plan.

## Steering record

The mid-project correction requires whitespace- and case-insensitive asset IDs and atomic
normalized-duplicate CSV rejection. It is captured here, in DEVELOPMENT.md, PLAN.md and
PROGRESS.md. The correction is implemented and verified throughout catalog, lending,
returns, CSV preview/apply, legacy migration and export recovery. Normalized duplicate
CSV batches fail atomically. Shared dashboards, authentication
and cloud sync explicitly remain deferred; the objective and local authority are unchanged.
