# 0007 — Calibrate acquisition before interpreting architectural comparisons

Date: 2026-09-30. This records the research-method and skill revision following the owner's
review of `40342dc`. The later autonomous execution and N-007 outcome are recorded in
[the calibration result](0008-calibration-result.md); the sections below describe the original revision.

## Decision and scope

Keep the repository and Rust runtime. Select **N-007: establish an informative learning
baseline** as the sole planned next item. Its objective is reliable task acquisition and
localization of transfer failures using an original learned system. The initial request
ended with delivery of this skill/docs revision; the owner subsequently authorized execution.

Preserve [EXP-0004's decision](0006-problem-representation.md), protocol, evidence and artifacts.
All four arms missed its acquisition floor; nineteen attempts completed verification and one
failed after fitting, with a separately labeled audit. The configuration remains rejected
and the broad H-011 comparison inconclusive. H-001/H-002 remain open but dormant.

The earlier requirement that representation success precede reusable computation is revised.
A competent original baseline can support a future recurrence or reuse experiment even if
conditional transport never wins. N-008 predictive state/compositional execution and N-009
procedure consolidation are conditional directions in the
[research program](../architecture/research-program.md), not active queue entries. No runtime
rewrite, learned halting, deeper physical ShardLoom integration or additional mechanism is
authorized by this document.

## What changes in experimental practice

The [evaluation contract](../evaluation.md) now separates an execution preflight from a
bounded development pilot and an untouched confirmatory comparison. A pilot may adapt within
its declared choices and total budget; it retains every attempt. For surface-transfer work,
the progression is tiny-set fitting, one-format generalization, mixed-format acquisition,
then unfamiliar transformations. Numeric stage gates and budgets belong in the executable
pilot protocol before fitting. A plan entry is not that protocol.

Training and validation accuracy, loss curves, per-format support and selection history must
make optimization failure, overfitting, encoding interference and transfer failure distinguishable.
New partitions must separate development from final evaluation and retire previously inspected
final examples. An uninformative acquisition result is not a verdict on the whole architecture.

Masked inputs, observed-change prediction, paired training views and useful architectural
biases are allowed, with disclosed provenance and equivalent control access. No pretrained
runtime intelligence or hidden exact solver is introduced. The program records primary-method
read scopes for predictive representations, relational bias, world models, algorithmic processors
and program libraries in the [source catalog](../research/sources.json); none is adopted as
Noetloom's foundation or evidence of its originality.

EXP-0004's averaging bottleneck is a development hypothesis. Its sequence and relation fields
have constant sums within each format, so uniform averaging loses the answer-bearing arrangement.
Input-dependent weights may still retain information; the failed raw-input controls also limit
attribution. Bypass or richer-intermediate ablations and task-relevant probes are bounded
diagnostics, not a predetermined architecture or a post-hoc explanation claimed as proven.

## Requirements still needing implementation

| Boundary | Current evidence | N-007 requirement |
| --- | --- | --- |
| Fitting telemetry | The representation worker collects losses and validation records, but writes `report.json` after native evaluation and restart checks. | Preserve fitting records before verification; separate fitting, verification and resource outcomes; demonstrate survival of an injected post-fit failure. |
| Training recovery | Saved parameter files contain weights and identity fields, without Adam/RNG/data-order state. | Call them parameter snapshots. Add exact training continuation only if needed and verified; inference restart is a different capability. |
| Artifact recovery | N-006 records about 105.6 MiB locally with no verified durable remote backup. | Establish an authorized second copy in a separate failure domain and an isolated restore/replay check before new unique checkpoints accumulate. |
| Learning admission | Existing preflight establishes throughput and implementation behavior. | Register and implement the acquisition pilot, search envelope, gates and confirmation boundary. |

These are prospective requirements, not repairs completed by changing documentation. Existing
drivers and artifact schemas remain as registered. The [storage contract](../storage.md)
requires complete preparation before any genuinely missing destination or publication decision
is surfaced; routine source/docs delivery retains standing authority. No weights were uploaded,
deleted or retrained as part of this revision.

## Milestones and boundaries

Track acquisition, transfer, retention, useful recurrence and procedural reuse separately.
Withdraw numerical estimates of the research landscape's exhaustion; no denominator supported
them. Keep the constrained learned-language, new-rule, new-composition and restart milestone
visible without claiming frontier parity. Keep ShardLoom's role at scoped evidence analytics
until a measured physical-state workload justifies more. The [plan](../state/plan.json)
remains the only execution queue.

## Revision verification

The Python suite passes all 111 tests (`python3 -B -m unittest discover -s tests -v`).
`python3 -B -m noetloom check` validates the plan, sources, links and existing contracts;
`python3 -B -m noetloom doctor` reports local harness admission ready. The skill-authoring
validator passes the three revised project skills and the versioned grounding entrypoint.
Its missing PyYAML dependency was supplied in isolated unsynced validation tooling, with
no project dependency or runtime change.

A read-only forward test exercised bounded pilot continuation, reuse eligibility after a
transport failure, interrupted verification/recovery, and docs-only scope. It exposed a
potential first-failed-trial stop; the wording now explicitly uses the admitted search limit
or registered early stop. A structural renderer check covered all 38,400 sequence/relation
order/query/dihedral combinations and confirmed the sums above; no learned model was evaluated.
Code, tests, registered experiment files and previous evidence/decisions are unchanged.
No new learning experiment or artifact restore was performed. Hosted checks are followed for
the delivered revision under the existing delivery workflow.
