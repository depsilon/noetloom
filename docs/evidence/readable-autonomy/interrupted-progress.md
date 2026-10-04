# ToolShelf progress and continuation

Current phase: **1 — catalog normalization correction**. Status: reopened. Not paused.

Phase 1's original implementation works: `add`, `inventory`, and `inventory --available` persist via SQLite.
Nine automated tests passed with Python 3.13. Actual separate-process commands and
no-write failures are retained in evidence/phase-1.txt. Preserve all implemented code,
tests, project guidance and source reference files.

Next action: implement one canonical trim/casefold asset-ID function in add and every lookup;
replace the old case-sensitive test; examine safe handling of any pre-correction database.
Run corrected catalog checks, then implement lending/returns/history/overdue with normalized
lookups, and CSV import with whole-batch normalized-duplicate rejection. Continue without
phase-by-phase permission. The first capability milestone was delivered to the parent.

Environment finding: `/usr/bin/python3` is 3.9.6, below the brief's Python 3.11+ minimum.
`/opt/homebrew/bin/python3.13` is available and all successful checks use it. README uses
`python3.13`; older CLI invocations now get a clear version error. No dependency was installed.

Input reconciliation: the mid-project user correction is **captured durably** in PROJECT.md,
DEVELOPMENT.md and PLAN.md. It is **not yet applied to source or tests**. The capture response
is being sent now; do not confuse captured with implemented. Superseded decision: case-sensitive
asset IDs. Current requirement: trim/casefold IDs everywhere, including commands and CSV;
normalized duplicate CSV batches fail atomically. Shared dashboards, authentication and cloud
sync remain deferred. No question or permission is pending. Preserve all files in reference/ and BRIEF.md. All application
work remains in this directory. There is no Git repository or remote delivery requirement.
