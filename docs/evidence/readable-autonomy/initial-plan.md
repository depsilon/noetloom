# ToolShelf implementation plan

This is the only active implementation queue. All phases include tests, inspection and repair.
The objective and authority are in PROJECT.md; implementation rules are in DEVELOPMENT.md.

## Phase 1 — Durable catalog and a usable command boundary

- **Outcome:** A volunteer can add uniquely identified named tools, list them and restart
  the process without losing data. Invalid and duplicate input cannot change the catalog.
- **Entry/dependencies:** The brief and workspace are understood; no application exists.
- **Scope/exclusions:** Python module entrypoint, error handling, inventory storage, schema
  ownership, add/list/available behavior. Lending commands and CSV transfer follow later.
- **Work:** Implement strict shared text/date validation, transactional SQLite access,
  `add` and `inventory`; prepare the relational loan schema required by the next phase.
  Keep read-only commands free of disk creation. Reject foreign databases and invalid input.
- **Relevant guidance:** DEVELOPMENT.md data and CLI contracts; PROJECT.md authority.
- **Acceptance:** Real separate CLI processes persist and read two assets; filtering
  available assets works; duplicates and bad names fail with original contents unchanged.
- **Verification:** `python3.13 -B -m unittest discover -s tests -v`; real CLI add/list/invalid
  requests against a temporary database, retained in evidence/phase-1.txt.
- **State/exit:** Complete. Nine tests passed and evidence/phase-1.txt records independent
  processes, restart persistence, available filtering and byte-identical failure rollback.
  The requested milestone now identifies PLAN.md and PROGRESS.md; phase 2 starts next.

## Phase 2 — Lending, returns and explicit-date overdue reporting

- **Outcome:** The volunteer can lend a tool, inspect current availability and loan history,
  return it, and lend it again without losing prior loans.
- **Entry/dependencies:** Phase 1 persistent inventory and CLI are verified.
- **Scope/exclusions:** `lend`, `return`, `loans`, and `overdue --as-of`; no reminders,
  borrower accounts or historical point-in-time inventory.
- **Work:** Enforce known tools, one active loan, due/lending/return chronology. Exercise
  exact due date boundaries, unknown assets, repeated returns, invalid dates and duplicate
  lending, including separate competing processes. Maintain stable sorting and useful tables.
- **Relevant guidance:** DEVELOPMENT.md data/CLI and lending/query sections.
- **Acceptance:** Borrow/return/reborrow preserves two loan IDs. Active inventory and history
  agree. Overdue requires an explicit valid date and excludes due-today loans. Every invalid
  transition leaves complete saved state unchanged.
- **Verification:** Full unittest suite with lifecycle, chronology and concurrency cases;
  real process CLI journey and failure checks retained in evidence/phase-2.txt.
- **State/exit:** Active. Phase 1 passed. Exit after lifecycle behavior and error paths pass,
  then proceed directly to phase 3.

## Phase 3 — Safe catalog transfer, recovery and complete delivery

- **Outcome:** A volunteer previews and imports a whole valid CSV batch, gets actionable
  row errors for invalid batches, and exports inventory/history plus a restorable snapshot.
- **Entry/dependencies:** Catalog and lending invariants from phases 1–2 are working.
- **Scope/exclusions:** Preview/apply CSV, ZIP export, usage instructions, complete integration
  checks and review. Shared systems, web UI and external effects remain deferred.
- **Work:** Implement strict complete-batch validation, content/catalog-bound preview tokens,
  transactionally rechecked apply, and consistent exports that cannot overwrite files.
  Write runnable README examples. Exercise initial catalog, CSV preview/apply, lending,
  overdue queries, return/reborrow, failures, export, and a restored database in real processes.
- **Relevant guidance:** DEVELOPMENT.md import/export and checks/review sections;
  reference/OPERATING-METHOD.md completion and continuation rules.
- **Acceptance:** Bad and stale batches cause no catalog additions; preview alone changes
  no disk state. Quoted Unicode CSV round-trips. ZIP contains complete inventory and history;
  its database snapshot can serve normal CLI queries with identical data. Documentation
  matches actual help and fresh-reader commands. No fixable review findings remain.
- **Verification:** `python3.13 -B -m unittest discover -s tests -v`; `python3.13 -B -m compileall -q toolshelf tests`;
  retained end-to-end transcript and exported recovery artifact under evidence/; final
  review and source identity recorded in VALIDATION.md.
- **State/exit:** Waiting on phase 2. Exit at the brief's local completion boundary, recording
  actual results, limits and any unanswered steering in VALIDATION.md and PROGRESS.md.

## Plan challenge

Every brief outcome maps to a phase and executable check. Persistence and safe failures
are established in the first useful slice; transition integrity and CSV atomicity are
tested where introduced. Recovery and instructions have explicit phase-3 acceptance.
No phase requires external authority. No separate repair backlog is maintained.
