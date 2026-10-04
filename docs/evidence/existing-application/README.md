# Autonomous maintenance of an existing application

Observed October 4, 2026 in a native Codex session. An agent extended the existing
ToolShelf application from a new outcome, derived two phases and completed 54 application
tests. All ten withheld acceptance cases then passed on the first run. The implementation
agent received neither a prepared implementation plan nor the independent cases.
This is a bounded maintenance exercise, not evidence of production-scale autonomy or a
controlled comparison with another development method.

## Starting point and separation

The starting application is the complete maintained [ToolShelf](../../../examples/tool-shelf/README.md)
at Noetloom commit `872e88c20c40fbada7603637633b063b282b4318`: seven application modules
(577 lines), three test modules, SQLite persistence and migrations, a public CLI, lending
history, atomic CSV preview/import, and restorable ZIP exports. Its 39 tests passed
before dispatch. [The inventory](baseline-sha256.txt) identifies the 52 copied files,
including ordinary project guidance and historical evidence. No application was scaffolded
for this exercise, and the original maintained example remains unchanged.

The [new objective](../../../examples/tool-shelf-renewals/NEW-OBJECTIVE.md) asks for loan renewal with explicit dates and persistent event history,
compatibility with old databases and recovery archives, unchanged existing report columns,
atomic rejection, concurrent-command safety, additive exports, and preserved catalog
preview behavior. It specifies the public interface and outcomes, not the database design,
code changes or phase breakdown. The agent owns inspection, planning, implementation,
regression coverage, integration and its final requirements review.

The implementation workspace contains the application, the new objective and the existing
plain-file method. The agent is instructed to use only that directory and ordinary local
tools: no parent repository, sibling acceptance files, original conversation, private
skills, plugins, Noetloom helpers, native discovery, network, dependency installation or
further agents. This is instructional isolation on a shared host, not an OS sandbox.
The implementation agent has no originating conversation. The primary retains experiment
design, independent acceptance, integration and final responsibility.

## Frozen acceptance

[Eight scenario families](acceptance-cases.md) were written from the objective before
dispatch. Their hashes, the objective, guide and baseline inventory were recorded at
20:53:40 UTC in [the initial receipt](pre-dispatch-sha256.txt). The separate executable
[acceptance runner](acceptance.py) was frozen at 20:59:33 UTC, before implementation
completion; [its receipt](runner-frozen-sha256.txt) identifies the exact bytes.

The runner uses actual subprocess CLI calls and independent version-1/version-2 database
fixtures. It does not import candidate modules or reuse candidate tests. Its ten cases
cover old reports and read-only access, normalized identity, chronology and due-date
boundaries, failed-write byte preservation, returned/reborrowed history, competing
renewals, complete recovery, catalog-preview compatibility, refused databases and old
recovery archives. It compares existing reports with the unchanged baseline application.

As a [negative control](baseline-negative-control.txt), all ten cases failed against the
unchanged baseline, with no test errors: the requested renewal interface was absent.
The candidate was first tested only after its native completion declaration. These cases
are a small independent sample of the requirements, not an exhaustive correctness proof.

## Derived work

The agent inspected the existing CLI, domain, storage, transfer and tests, reran all 39
baseline tests, and derived two extension phases in the existing plan. It preserved the
three completed original phases as history. Phase 4 covers renewal, persistent history,
chronology and legacy compatibility; phase 5 covers exports, recovery, concurrency,
regressions and integrated acceptance. [The initial plan](derived-plan-at-start.md) was
captured at 21:00:05 UTC after its notification, with [a source receipt](plan-observation.txt).
The notification requested no approval, and no subsequent task selection or implementation
steering was supplied.

The agent proceeded from inspection through both phases without another instruction.
Application tests advanced from 39 to 48, then 53. After that integrated result, the agent
compared the original requirements with source, actual CLI behavior, documentation and
the three retained prior recovery archives. It added a rollback check using a real SQLite
trigger to fail a due-date update after event insertion; the event and older-schema
upgrade both roll back. The final suite passed 54 tests with resource warnings enabled.
The full journey, 26 runnable README commands, three prior archives and compileall passed.
Its [validation record](../../../examples/tool-shelf-renewals/VALIDATION.md) retains the
commands, artifacts, requirements-to-proof mapping and same-session review findings.

## Completion and independent results

After the native declaration, the primary copied all 76 candidate files without editing
them. [The completion receipt](native-completion.txt) and
[candidate inventory](native-candidate-sha256.txt) identify this snapshot. At 21:17:12 UTC,
the frozen runner tested that snapshot: **10 tests passed in 4.290 seconds**.
[The first output](first-acceptance.txt) preserves the result and both source identities.
The candidate's complete file inventory and bytes were identical before and after the run.
No case was changed or disclosed to the implementation agent before completion.

| Discovery stage | Findings and disposition |
| --- | --- |
| Native development | No application defect was reported by the executed checks. Existing version assertions and a legacy fixture were updated for the additive schema. |
| Native final requirements review | No application defect found. One documentation finding, FA-1: stale continuation text still called the old 39-test result current. The agent repaired it before declaring completion. The injected storage failure was a passing negative test, not a discovered bug. |
| Independent acceptance | All ten frozen cases passed on the first candidate; no application repair was needed. |
| Primary integration review | Inspected transaction/migration boundaries, stable IDs, report/export consistency and changes to original assertions. No additional application defect found; the maintained application is the unmodified native candidate. |

The original three test modules and their test methods remain; changed old assertions
track the schema version and additive archive member. The new module and extended
transfer tests cover the new requirements. The primary also inspected the independent
runner's failure controls and kept its original bytes. No concrete missing or contradictory
framework instruction was observed, so the operating method, canonical skills, helpers,
templates and plugin contents remain unchanged.

The maintained result is [examples/tool-shelf-renewals](../../../examples/tool-shelf-renewals/README.md).
The parent suite runs its actual 54-test application suite and the independent ten-case
runner. Replay the latter from the repository root with ordinary Python 3.11+:

```sh
python3 -B docs/evidence/existing-application/acceptance.py \
  --project examples/tool-shelf-renewals --baseline examples/tool-shelf
```

[Current fingerprints](source-sha256.txt) bind the complete maintained example and this
observation's files. The pre-dispatch inventory, initial plan and first candidate inventory
remain distinct. Parent integration checks and hosted results belong to
[the validation record](../../validation.md).

## Limits

This is one existing application with seven small modules, real persistence and public
compatibility obligations. It is more demanding than scaffolding, but it is not a mature
production codebase, a long-running maintenance campaign or a causal measurement of the
method's benefit. The same native session performed implementation and its final review;
the separate primary authored the withheld cases before seeing the finished implementation.
Both agents share a host and base model family, and the boundary was instruction-enforced.

Native execution and first independent acceptance used Python 3.13 on macOS. Hosted tests
exercise resulting code; they do not replay planning or establish native execution in
Claude or another host. No deployment, background operation, power-loss simulation,
disk-full test or large-library benchmark was performed. Existing filesystem and legacy
collision limits remain documented in the application. Source hashes preserve identities
and detect drift; they do not authenticate the observation or replay the agent.
