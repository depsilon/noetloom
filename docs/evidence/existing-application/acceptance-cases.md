# Frozen independent acceptance cases

Frozen before implementation for the existing ToolShelf renewal exercise. The implementation
agent receives only the existing application, readable method and NEW-OBJECTIVE.md. These
cases and their eventual executable runner remain outside its workspace until after it
declares completion. Primary acceptance owns these checks; they are not additional product
requirements. Tests exercise public CLI behavior and real files, not implementation helpers.

Baseline: examples/tool-shelf at Noetloom commit
872e88c20c40fbada7603637633b063b282b4318. Preserve the baseline source manifest. The baseline
suite must pass before the autonomous change starts. No prepared implementation plan,
solution, new framework skill, helper, plugin or repeated user task selection is supplied.

1. Legacy compatibility: construct a version-2 database with active and returned loans
   using the unchanged baseline, and a valid version-1 database with normalized-reference
   migration needs. Compare original inventory/loans/overdue output to the new program.
   Read-only renewal history and export leave original bytes unchanged.
2. Renewal lifecycle: padded mixed-case/Unicode IDs address the same active loan.
   Two increasing extensions preserve loan identity, borrower and start date, append
   ordered history with correct old/new dates, and change current reports and the exact
   overdue boundary. Include a renewal after the previous due date.
3. Rejected requests: equal/shorter due date, invalid/empty dates, new due before renewal,
   renewal before lending or earlier renewal, unknown/unloaned asset and repeated extension
   all fail with complete saved bytes unchanged. Include rejection on an old schema.
4. Return and reborrow: an early return before the last renewal fails unchanged; a valid
   return and later loan work. Closed-loan renewal fails. Earlier history stays attached
   to the earlier loan, with normalized history filtering.
5. Competing renewals: two simultaneous identical extensions yield one success, one
   rejection, one history event and one final due date. Database integrity and unrelated
   rows remain valid.
6. Recovery: export the renewed application, inspect the preserved CSV headers and
   renewal CSV, restore the database under a new name and compare public query output.
   Existing destination bytes cannot be replaced. Old snapshot recovery also remains usable.
7. Catalog independence: a preview created before a renewal can still apply unchanged;
   normalized duplicate batches remain atomic failures. Catalog and old report formats
   otherwise remain compatible.
8. Refusal and absence: foreign/unknown-version databases and legacy ID collisions stay
   unchanged on rejected reads/writes; renewal on a missing database creates nothing.
   Reading empty history also creates no database.

The executable acceptance harness may use concrete fixtures and permutations within
these cases. Freeze its source before the implementation completion report; any later
runner repair must be explained and cannot silently change the case expectations.
Run after the agent declares completion. Record each first result before repairs.
Separate defects observed during development, first found in the agent's final review,
and first found by independent acceptance or integration. A green suite is evidence for
these cases, not universal correctness or a causal Noetloom-performance claim.

If a check finds a defect, preserve the first failing output, repair the scoped application,
add regression coverage and rerun affected acceptance. Change framework instructions only
if the exercise reveals a specific missing or contradictory instruction; do not duplicate
an existing rule just because an implementation missed it.

