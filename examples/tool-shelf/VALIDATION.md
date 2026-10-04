# ToolShelf validation and completion evidence

## Current maintainer acceptance

The native fresh session completed all three phases with 36 passing tests. During
integration, independent primary review found that control validation happened before
asset-ID trimming: tab/newline-padded IDs were rejected despite the accepted correction.
A new CLI regression first failed with that exact error. The shared identity function
now trims the boundary before rejecting remaining internal controls. Catalog, lending,
return and CSV normalization/collision regressions pass; name/borrower controls remain
invalid. The plan and guidance were updated within the existing objective.

- `python3.13 -B -m unittest discover -s tests -v`: **39 tests passed** on macOS.
- `python3.13 -B scripts/verify_journey.py`: passed again after the repair; current
  [transcript](evidence/journey-ugolnj__/transcript.txt) and
  [recovery archive](evidence/journey-ugolnj__/recovery.zip) are retained.
- The existing-file overwrite test always runs. A separate symlink-creation test is
  skipped on Windows because unprivileged symlink creation is host-dependent; macOS ran it.
- [Current source hashes](evidence/source-sha256.txt) describe this maintained version.
  [Native-session hashes](evidence/native-session-sha256.txt) preserve the earlier identity.
  The records below describe the native session at that earlier milestone. Broader CI
  observations belong to the parent repository's validation record.

All local acceptance is complete. Deferred features and authority remain unchanged.

## Original phase 1 — historical evidence

Historical milestone: catalog completion is now reopened for the accepted case-insensitive
ID correction. The original case-sensitive test is superseded; other phase-1 evidence remains
useful. Corrected source and tests have not yet run at capture time.

- `python3 -B -m unittest discover -s tests -v`: initial environment check failed because
  this machine's default Python is 3.9.6. No application test executed under that interpreter.
  Located the already installed Python 3.13; added a clear unsupported-interpreter CLI error.
- `python3.13 -B -m unittest discover -s tests -v`: **9 tests passed**. Coverage includes
  separate-process persistence, unique IDs, trimming/Unicode, invalid input with no created
  DB, nonmutating reads, foreign/unsupported DB refusal and strict real calendar dates.
- Actual subprocess journey is retained in [evidence/phase-1.txt](evidence/phase-1.txt).
  Two assets persisted; available inventory listed both; duplicate and blank-name requests
  exited 1 and the stored database was byte-identical before and after each failure.

Evidence applies to the phase-1 application and test sources at this milestone. Final
validation will record a content identity for the completed source.

## Agreed final boundary

Python 3.11+ standard library only; complete local CLI, automated tests, readable usage,
actual full volunteer journey and failure checks, CSV atomicity and exported recovery.
No network, third-party installs, other host execution, publication or deployment.

## Corrected catalog and lending milestones

- `python3.13 -B -m unittest discover -s tests -v`: **11 tests passed** after the
  catalog correction, then **17 tests passed** after lending integration.
- Added tests verify trim/casefold identity, Unicode collisions, version-1 reads without
  writes, atomic version-1 normalization with loan references, and legacy collision refusal.
- Lending tests verify real-process return/reborrow with stable loan IDs, current availability,
  borrower trimming, chronological validation, explicit and exclusive overdue dates, default
  local dates, and simultaneous competing processes with exactly one successful loan.
- All tested invalid transitions leave saved database bytes unchanged. Unknown loans and
  reads on an absent database leave no database or temporary artifact.
- Real commands and inspected outputs are retained in evidence/phase-1-corrected.txt and
  evidence/phase-2.txt. These milestones do not yet prove transfer or recovery completion.

## Final delivery — complete on 2026-10-04

Actual execution used this macOS host and Python **3.13.13**. No dependency was installed.
The CLI, domain, SQLite storage, transfer, tests and README are complete. The accepted
trim/casefold correction is applied throughout, not merely captured in documents.

| Check actually executed | Result |
| --- | --- |
| `python3.13 -B -m unittest discover -s tests -v` | **36 tests passed**, final run 3.243 seconds |
| `python3.13 -B -m compileall -q toolshelf tests` | Exit 0 |
| `python3.13 -B scripts/verify_journey.py` | Full CLI journey and every recovery/failure assertion passed |
| README shell examples, with only filenames and the printed token substituted | **18 CLI commands exited 0**, restored inventory/history matched |
| `python3 -B -m toolshelf --help` | Expected exit 1 with a clear Python 3.11+ requirement; no traceback |

The final suite includes 12 catalog, 6 lending and 18 transfer tests using real SQLite
and actual subprocesses. It checks normalized duplicates; legacy read/migration and
collision refusal; invalid input and absent-file behavior; return/reborrow IDs; exclusive
overdue dates; complete saved-byte comparisons; two competing lenders/imports/exports;
malformed and stale CSV; physical row errors; cleanup on export failure; existing-file
and symlink refusal; and snapshot consistency during separate-process loan changes.

The final journey and artifacts are retained in
[evidence/journey-tosu30mg/transcript.txt](evidence/journey-tosu30mg/transcript.txt):

- Five tools survive process restarts, including a quoted Unicode name and a casefolded
  `Straße` ID. Duplicate/invalid requests and CSV previews preserve saved bytes.
- A changed catalog and changed file each reject their stale confirmation. A batch with
  valid rows plus normalized duplicate, existing-ID, empty-cell and extra-field errors
  imports nothing and prints actionable line numbers.
- A loan due on the explicit query date is absent from overdue output. A later query
  includes it. Return/reborrow retains loan IDs 1 and 2; another tool receives ID 3.
- [recovery.zip](evidence/journey-tosu30mg/recovery.zip) has `catalog.csv`, `inventory.csv`,
  `loans.csv`, `library.sqlite3` and `RESTORE.txt`. It includes three loans: one closed,
  two active. A repeated export leaves the archive byte-identical.
- The extracted `restored.sqlite3` produces identical inventory, history and overdue
  output, passes `PRAGMA integrity_check` and has no foreign-key violations. Importing
  `catalog.csv` into a different new database preserves every ID and name.

[evidence/readme-check.txt](evidence/readme-check.txt) retains actual commands and output
for all 18 runnable CLI examples. Its first ad-hoc selector accidentally counted the
`compileall` development command as a CLI example; that harness assertion was repaired
to select `-m toolshelf` specifically, and the corrected check passed. This was not an
application failure. The earlier complete journey in `evidence/journey-wvl95v4f/` is
preserved; `journey-tosu30mg` is the final-source rerun after review repairs.

## Adversarial review and repairs

The final review inspected input boundaries, SQLite transaction scope, migration
rollback, competing-process behavior, snapshot provenance, archive publication and actual
CLI output. The comparator was a conservative local data utility that preserves the
volunteer's existing records on failed requests. It was a same-agent source and behavior
review, not an independent or external audit.

The review fixed explicit empty `--on` values silently selecting today, missing database
parents being treated as empty libraries, Unicode line separators passing single-line
validation, and export targeting the absent database path itself. Legacy read snapshots
commit their in-memory normalization before use by the backup API; the integration test
confirms preview/export do not alter legacy files and stale apply rolls migration back.
Queries and previews remain read-only; successful initial writes publish complete files.
No known fixable finding remains within the agreed local boundary.

## Source identity and limits

[evidence/source-sha256.txt](evidence/source-sha256.txt) identifies application sources,
tests, the journey script, README, project owners and preserved reference material.
It excludes this validation record, the progress receipt and generated artifacts to
avoid a circular checksum. No Git repository or commit was required.
The manifest's SHA-256 is `48cc36eccec5d253bee40e4577db9acd47520236d5d5ad63dd471e48dc48adf3`.
The final recovery archive's SHA-256 is
`c44f9017bcd84f00ca1fe62c43c0ac0adc1c052eebfd52e7d98c59fbe6e778d3`.

Functional tests and journeys ran only under Python 3.13 on this macOS host; Python 3.9
was exercised only for its version-rejection message. Python 3.11/3.12 and other
operating systems were not executed. No power-loss simulation or large-scale performance
benchmark was run. New-file publication needs same-directory hard-link support; it was
verified on this local filesystem. Unsupported filesystems should report a local-file
error rather than use an overwrite fallback.

The first corrected catalog/lending test runs inherited OS-temporary fixture placement;
those fixtures were removed by the tests. Subsequent tests were changed to create their
temporary files under this workspace's `evidence/`. All retained artifacts are here.
No external project records, private/global skills, reference-kit source, native skill
discovery directories, framework commands, subagents, network calls, model APIs, third-party
installs, publication, deployment, remote writes or messages to people were used.

Legacy normalized-ID collisions require explicit local data repair from a preserved backup;
the app intentionally cannot choose which tool to discard. CSV is raw transfer data, not a
spreadsheet sanitization format; database recovery, rather than catalog import, restores
loan history. Borrower data relies on local filesystem access control. Shared dashboards,
authentication, cloud sync, web interfaces and notifications remain deferred. No requirement,
question, permission or implementation item is outstanding at this boundary.
