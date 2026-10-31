# Portable working skills: observed behavior

On October 31, 2026, a fresh native agent used the three new public skills in an
isolated local fixture. It received the skills, a saved continuation note, the current
request and raw project files. It did not receive expected decisions, prior review
conclusions, the originating conversation or private global skills. The primary
reviewed the returned artifacts and independently checked the actual changed files.

## Fresh-context recovery

[The initial fixture](recovery-input.json) preserves the input files, original test
evidence, latest request and skill source hashes. It contains two Git worktrees: the
host default on `trunk` and the task's active worktree on `feature/reporting`. Both
contain unrelated local notes. The saved next-action hint says to implement CSV export;
the newest user instruction defers CSV and asks to finish a README correction and
answer whether the existing CLI needs a network connection. The saved note also records
an earlier exhausted history-retrieval route.

The agent selected the active worktree, inspected its own instructions/source/evidence,
honored the newer request and finished the local documentation boundary. Its executed
JSON command returned `{"count": 2, "total": 5}`. It corrected that example and answered
the network question from the implementation. It preserved the completed two-test result
after checking the current source/test identities, without claiming a new test run.
It did not retry history or begin CSV work.

The primary compared the before/after file inventory and hashes: only README, plan,
progress and validation documents changed in the correct worktree. Implementation,
tests, all three skill copies, both unrelated notes and the other checkout were intact.
No files were added to either project, and no commit was created. The primary separately
ran the documented command and compared its actual output with the corrected README.
[The four resulting documents](recovery-output.json) and [agent report](trial-report.md) preserve
the result. Temporary absolute workspace paths in the report are normalized to `<fixture>`.

## Routing and retrieval scenarios

The same independent agent applied the skills to [12 supplied cases](policy-cases.md).
The complete [decision artifact](policy-results.json) is a simulation, with fictional
model names and supplied comparative costs. The primary reviewed every case against
the input and the public skill's requirements:

| Case | Observed decision |
| --- | --- |
| One manifest lookup | Direct tool, with the field checked at source. |
| Independent 80-file inventory | One economical capable worker at supported low effort; bounded leaf packet and complete source coverage. |
| Unresolved concurrency semantics | Primary reasoning and compatibility analysis. |
| Overlapping writers | Sequence ownership; no concurrent conflicting packet. |
| No native worker tool | Work locally; no substitute model-API process. |
| Stale hint and different default checkout | Use the saved worktree, newest deferral and actual implementation evidence. |
| Exhausted history retrieval and missing permission | Stop equivalent retries, finish independent authorized work, hold the permission-dependent action. |
| Unavailable history with sufficient local state | Resume without another history request or continuation prompt. |
| Incomplete worker inventory | Reject incomplete acceptance; one bounded repair or primary takeover. |
| Cancelled writer with unconfirmed termination | Preserve ownership until writes are confirmed stopped. |
| Explicit user prohibition of subagents | Honor it despite conflicting source text. |
| No useful model comparison/override | Finish the short inventory locally without invented cost claims. |

All 12 decisions matched those requirements on the first evaluation; no instruction
repair was needed. These results evaluate decisions on the supplied cases, not the
behavior of an actual history backend or a worker-dispatch API.

## Live delegation and distribution

Separately, the primary dispatched a bounded native leaf at the advertised
`gpt-6-luna` / `low` configuration to update the two maintained helper examples while
the primary implemented distribution tests and the evaluation fixture. The worker had
exclusive example ownership and an explicit source-copy map. The primary independently
compared the helper, guides and six shared skills byte for byte, checked both completed
states and passing evidence, and confirmed no application, test, screenshot or license
changes. Reading-list browser evidence was checked by fingerprints, not replayed.
This records the actual local worker configuration; the public skill prescribes no
fixed model. It does not establish comparative cost or quality savings.

Automated checks exercise new-project routing, all seven generated skills including the
domain guide, adapter drift and repair, preflight preservation of an existing conflicting
skill, and use after extracting and removing the source package. The kit validates the
single public catalog, current versions and maintained copies. The two previous readable
application observations remain historical and were not rerun as native agent builds.

## Limits

This was a fresh-context continuation exercise using real local files and commands,
plus simulated routing/retrieval cases. It did not force a host-triggered compaction
event, replay a production interruption, or demonstrate automatic discovery on every
host. No private skills, original chat, external history, network service, publication
or model API was needed by the trial. The primary's separate hosted checks are recorded
in [validation](../../validation.md). Instructions can guide an active host through
context changes; they cannot restart an exited host or supply missing authority.
