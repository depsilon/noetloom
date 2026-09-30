# Evaluation and claim contract

## State the claim before selecting the test

A protocol links a falsifiable question to observations, data, candidates, controls, costs,
acceptance criteria, and a stopping rule. The current
[EXP-0001 protocol](../experiments/EXP-0001/protocol.json) and
[Python validators](../noetloom/contracts.py) define the bootstrap's supported format.
The harness execution path admits only `harness_validation` for `mutable_recall_v1`. Unknown keys and versions,
oversized workloads, network access, pretrained components, and training requests are refused.
These validators implement specific contracts; they are not a general JSON Schema engine.

The separately registered [EXP-0002](../experiments/EXP-0002/design.md) uses
`noetloom.learning.v1`, a strict instance-specific contract and a separate driver. It
records learned selection, payload encoding, controls, held-out structures, and measured
cost. The information below governs learned experiments; harness evidence remains distinct.
The follow-up [EXP-0003](../experiments/EXP-0003/design.md), `noetloom.allocation.v1`, freezes
own-trained parent readers and evaluates a learned allocation gate. It charges inherited
fitting and new acquisition separately and retires the previous experiment's test examples.

| Dimension | Required evidence for a learned experiment |
| --- | --- |
| Provenance | Source revision, environment, data/generator versions, rights, transformations, teacher assistance, initialization and seed identities |
| Observation | Exact inputs, labels, state access, reset boundaries, and which components are learned or hand-written |
| Selection | Training/validation/test isolation; tuning attempts, selected checkpoint rule, and frozen final evaluation |
| Comparison | Credible learned baseline and mechanism ablations with matched information, training/tuning budget, and inference constraints |
| Generalization | Held-out task structures/compositions, capacity and delay shifts, and independent tasks when claiming broader transfer |
| Continual learning | Retention, interference, adaptation cost, erroneous-update recovery, and state/parameter growth |
| Cost | Wall time, peak memory with measurement scope, stored bytes, bytes read/written where relevant, and acquisition/selection/verification overhead |
| Uncertainty | Multiple independent training seeds; per-seed results and interval method with the actual independent sampling unit |
| Decision | Preregistered useful effect, budget/stop rules, failures, deviations, and retain/revise/reject reasoning |

Do not compute confidence as if correlated tokens, queries from one episode, or checkpoints
from one training run were independent training trials. Preserve per-seed and per-task
results. Define missing-data and failed-run handling in advance. Never drop bad seeds silently.
If a test set informed a design decision, retire it from unbiased final evaluation or label
the reuse and introduce a new held-out set.

## What EXP-0001 measures

Every episode writes randomly assigned values to a shuffled set of keys, queries them,
inserts distractors, queries delayed values, revises some bindings, deletes disjoint bindings,
and queries a never-observed key. Revised values always differ from their originals.

All controls see the same operations. Expected answers and phase labels stay in the scorer.
Query keys are available to the predictor; the scorer alone stores the expected current value.
Controls start empty in every episode:

| Control | Behavior | Diagnostic role |
| --- | --- | --- |
| `exact_memory` | Stores current bindings and obeys deletions | Positive reference; every answer must be correct |
| `no_memory` | Stores nothing and always returns unknown | Detects a scorer/task that rewards absent recall |
| `stale_memory` | Keeps the first write and ignores deletions | Must expose both revision and deletion failures |
| `bounded_memory` | Keeps a fixed number of bindings, evicting the least recently written | Detects loss when distractors or working sets exceed capacity |

The report includes per-split, per-phase counts and per-query predictions. Acceptance requires
the exact reference to be perfect, all three negative controls to make errors, phase-specific
stale/absent-memory checks, a delayed-recall capacity failure, and no duplicate complete
episode input streams. The overlap check hashes actual observations, excluding phase labels
and split identities. It detects literal input duplication, not conceptual leakage.

The split name contributes to deterministic generation but is never a control input. Development,
validation, and test share a task template; `capacity_shift` increases slots and distractors.
These are fixed-generator diagnostics, not evidence of learned semantic generalization.
There is no fitting, optimization, language model, persistent cross-session state, or learned
procedure in this experiment. Aggregate control accuracy is not a benchmark of intelligence.

## Verification and proof limits

`verify-run` first checks the exact file inventory and all payload sizes and hashes, then
requires matching runtime source and regenerates every prediction and score. It refuses
incomplete evidence, source drift, altered rows, fabricated summaries, and a stored policy
that exceeds the current host's admission. A verified run may have a failed harness verdict.

The verifier shares the generator and scorer with the runner. Replay catches result drift,
but shared bugs require separate tests with manually known expected outcomes. Unit tests
therefore check operation semantics, label separation, negative-control sensitivity, overlap
rejection, resource refusal, and tampering both before and after manifest hashes are recomputed.
Checksums are not authentication; timing and resource observations are structurally checked,
not independently remeasured by replay.

Compact evidence kept in Git must identify the complete run by manifest hash and source digest,
state where payloads are retained, and accurately describe retrievability. Do not imply a
machine-local run is already available from GitHub. Repeat the deterministic harness when
source changes invalidate prior evidence; preserve the old identity rather than relabeling it.
