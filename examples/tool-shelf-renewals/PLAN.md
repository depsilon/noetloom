# ToolShelf implementation plan

This is the only active implementation queue. All phases include tests, inspection and repair.
The objective and authority are in PROJECT.md; implementation rules are in DEVELOPMENT.md.

## Current extension — loan renewal history

NEW-OBJECTIVE.md supersedes the previous completion checkpoint for this local extension.
The extension is complete at the local boundary on 2026-10-04; no active work remains.
The baseline is the functioning version-2 application: all 39 existing tests passed again
before edits (`evidence/renewal-baseline.txt`). Keep the CLI/domain/storage/transfer split,
SQLite writer lock, canonical identity, catalog preview binding and exclusive publication.
Historical phases below remain evidence of the original build, not outstanding work.

### Phase 4 — Atomic renewals across current and older libraries

- **Outcome:** A volunteer extends the same active loan with explicit dates, sees its
  ordered renewal history and current due date, and cannot erase history or reverse chronology.
- **Entry/dependencies:** Baseline inspected and 39 tests passing; ready now.
- **Scope/exclusions:** Schema version 3, in-memory old-version read upgrades, transactional
  write upgrades, `renew`, `renewals`, and latest-renewal return validation. No new loan model,
  new dependencies, historical inventory reconstruction or change to existing report columns.
- **Work:** Store append-only events keyed by stable renewal IDs and referencing loan IDs.
  Keep the current due date on the loan. Under one `BEGIN IMMEDIATE`, validate the current
  active loan and latest renewal, append the old/new due-date event and update the loan.
  Upgrade version 1 via canonical identity then add version-3 history; version 2 only needs
  history. Reads upgrade memory only; every rejected write must roll back the upgrade.
- **Relevant guidance:** DEVELOPMENT.md data/CLI and renewal rules; PROJECT.md authority;
  NEW-OBJECTIVE.md dates, history and compatibility requirements.
- **Acceptance:** Real CLI renewals preserve loan ID, borrower and lending date; history
  has the specified TSV columns and normalized filtering. Same-day renewals/returns work,
  overdue renewal is allowed, invalid transitions preserve bytes, and old IDs survive upgrade.
- **Verification:** New CLI/SQLite renewal tests for lifecycle, strict dates, missing flags,
  duplicate extensions, chronological limits, read-only version-1/version-2 queries, failed
  upgrades and successful upgrades; run the full regression suite and retain command output.
- **State/exit:** Complete. `evidence/renewal-phase-4.txt` records 48 passing tests,
  including nine new real-CLI renewal/compatibility cases. Version-1/version-2 failed
  upgrades preserve bytes; successful renewal keeps sparse loan IDs and sequence state.
  No product defect was exposed by this first implementation check. Proceed to phase 5.

### Phase 5 — Recovery, competing commands and complete local acceptance

- **Outcome:** Renewals survive exports/restores and competing processes; volunteers and a
  fresh developer have accurate usage and continuation instructions.
- **Entry/dependencies:** Phase 4 lifecycle and upgrade behavior verified.
- **Scope/exclusions:** Additive `renewals.csv`, consistent recovery snapshots, renewal-aware
  concurrency and preview regressions, runnable journey and docs. Preserve all original CSV
  headers/entries, prior recovery snapshots and deferred scope; no external delivery.
- **Work:** Derive all archive files from the same immutable backup; add renewal recovery
  instructions. Exercise duplicate/different concurrent renewals and return races, old recovery
  artifacts, preview tokens across renewal-only changes, and source byte preservation. Update
  README, project owners and continuation. Perform a final requirement-by-requirement review
  after implementation checks; record any first-found acceptance defects separately from
  development failures and repair them before closing this phase.
- **Relevant guidance:** DEVELOPMENT.md import/export and checks/review; NEW-OBJECTIVE.md;
  reference/OPERATING-METHOD.md completion obligations.
- **Acceptance:** Current/old restored queries match their snapshots; each successful concurrent
  extension forms one valid event transition, and no event is lost. Existing imports and errors
  remain intact. Fresh-reader examples run. All requirements have observed proof and no known
  fixable defect remains at the local boundary.
- **Verification:** `python3.13 -B -m unittest discover -s tests -v`, resource-warning run,
  `python3.13 -B -m compileall -q toolshelf tests scripts`, extended
  `python3.13 -B scripts/verify_journey.py`, actual README examples, and final same-session
  acceptance review. Retain transcripts, recovery artifacts, failure categories and source hashes.
- **State/exit:** Complete. Integrated suite: 53 tests; final suite including a real SQLite
  mid-operation failure: 54 tests passed with resource warnings enabled. The retained CLI
  journey, 26 README CLI examples and three actual prior recovery archives passed. Final
  same-session requirements review found no runtime defect and corrected stale continuation
  wording (FA-1 in VALIDATION.md). The six-entry archive restores all events and accepts a
  further renewal with preserved IDs. No known fixable issue or external delivery remains.

### Extension plan challenge and decisions

Every new outcome has an owner: phase 4 owns dates, retained identity/history and safe upgrades;
phase 5 owns archive integration, concurrency, preview compatibility and delivery. The first
phase exercises real CLI behavior immediately. Event asset IDs are read through their immutable
loan reference, avoiding duplicate asset state. Unknown but syntactically valid history filters
produce an empty report, like other report filters; `renew` still rejects unknown assets.
No external authority or unresolved user choice is needed. Keep the original deferred features.

Final review checked every NEW-OBJECTIVE.md requirement against source and executable
evidence, including intentional database failure after event insertion. The transaction
rolled back both event and older-schema upgrade with saved bytes unchanged. No product
defect was found during development or final acceptance. FA-1 was a documentation finding:
PROGRESS.md still included a superseded 39-test milestone described as current. Replaced
that continuation with the actual completed extension; historical evidence stays below and
in VALIDATION.md. There is no separate audit or repair queue.

## Original completed build — historical plan

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
