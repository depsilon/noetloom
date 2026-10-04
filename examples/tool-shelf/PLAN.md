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
- **State/exit:** Complete, including the maintainer's whitespace-boundary repair and
  catalog/lending/CSV regressions; the integrated suite now passes 39 tests. Surrounding
  tabs/newlines are trimmed before internal controls are validated. Historical milestone: eleven corrected
  catalog checks passed, including Unicode casefolding, duplicate no-write failures,
  collision-free legacy migration and legacy collision refusal. The original nine-test
  milestone and evidence/phase-1.txt remain historical evidence; corrected CLI evidence
  is in evidence/phase-1-corrected.txt. Phase 2 may proceed.

## Phase 2 — Lending, returns and explicit-date overdue reporting

- **Outcome:** The volunteer can lend a tool, inspect current availability and loan history,
  return it, and lend it again without losing prior loans.
- **Entry/dependencies:** Phase 1 persistent inventory and CLI are verified.
- **Scope/exclusions:** `lend`, `return`, `loans`, and `overdue --as-of`; no reminders,
  borrower accounts or historical point-in-time inventory.
- **Work:** Enforce known tools, case/whitespace-insensitive ID lookup, one active loan,
  due/lending/return chronology. Exercise
  exact due date boundaries, unknown assets, repeated returns, invalid dates and duplicate
  lending, including separate competing processes. Maintain stable sorting and useful tables.
- **Relevant guidance:** DEVELOPMENT.md data/CLI and lending/query sections.
- **Acceptance:** Borrow/return/reborrow preserves two loan IDs. Active inventory and history
  agree. Overdue requires an explicit valid date and excludes due-today loans. Every invalid
  transition leaves complete saved state unchanged.
- **Verification:** Full unittest suite with lifecycle, chronology and concurrency cases;
  real process CLI journey and failure checks retained in evidence/phase-2.txt.
- **State/exit:** Complete. Seventeen total tests pass, including real separate-process
  lifecycle and competing loans, chronology, due-date exclusivity, normalized lookups and
  byte-unchanged invalid transitions. CLI evidence is in evidence/phase-2.txt. Proceed
  directly to phase 3.

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
- **Acceptance:** Bad and stale batches cause no catalog additions, including IDs that collide
  only after trimming/casefolding within the batch or with existing data; preview alone changes
  no disk state. Quoted Unicode CSV round-trips. ZIP contains complete inventory and history;
  its database snapshot can serve normal CLI queries with identical data. Documentation
  matches actual help and fresh-reader commands. No fixable review findings remain.
- **Verification:** `python3.13 -B -m unittest discover -s tests -v`; `python3.13 -B -m compileall -q toolshelf tests`;
  retained end-to-end transcript and exported recovery artifact under evidence/; final
  review and source identity recorded in VALIDATION.md.
- **State/exit:** Complete at the agreed local boundary. The native session finished with
  36 tests and compileall passing; maintainer acceptance now passes 39 tests after the
  whitespace repair and portable symlink-test separation. A fresh real-process journey in
  evidence/journey-ugolnj__/ verifies atomic invalid/stale imports, lending and failure
  paths, no-overwrite export, identical restored queries and quoted Unicode catalog
  round-trip. Eighteen README CLI examples were executed successfully. Inspection and
  adversarial review repaired the identified boundary cases; no known actionable findings
  remain. VALIDATION.md records source identity, exact checks and execution limits.

## Plan challenge

Every brief outcome maps to a phase and executable check. Persistence and safe failures
are established in the first useful slice; transition integrity and CSV atomicity are
tested where introduced. Recovery and instructions have explicit phase-3 acceptance.
No phase requires external authority. No separate repair backlog is maintained.

Accepted steering: ID normalization reopens only affected catalog semantics and dependent
lending/import checks. Preserve unrelated evidence. Shared dashboards, authentication and
cloud sync remain deferred. Resolve this in the existing phases; do not create a second queue.

Parent Windows CI exposed open SQLite handles in the test fixtures. Explicit connection
closure repairs that test-lifecycle defect; all 39 cases pass locally with resource warnings
enabled. The application behavior and completed native exercise remain unchanged. The
parent repository owns the cross-platform rerun and remote delivery.

The maintainer review repairs and all authorized local phases are complete. There is no
permission question. A new session should confirm newer steering before selecting new work.
