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
The [EXP-0004 comparison](decisions/0006-problem-representation.md) was inconclusive
because all arms missed its acquisition floor; one attempt also failed after fitting.
The development requirements below apply to subsequent work. They do not change any of
these registered protocols, runs or historical decisions.

| Dimension | Required evidence for a learned experiment |
| --- | --- |
| Provenance | Source revision, environment, data/generator versions, rights, transformations, teacher assistance, initialization and seed identities |
| Observation | Exact inputs, labels, state access, reset boundaries, and which components are learned or hand-written |
| Selection | Bounded development search, training/selection/final isolation, all tuning attempts, checkpoint rule, and frozen final evaluation |
| Acquisition | Task-appropriate fitting and generalization gates, learning curves, training/validation metrics and per-format support |
| Comparison | Credible learned baseline and mechanism ablations with matched information, training/tuning budget, and inference constraints |
| Generalization | Held-out task structures/compositions, capacity and delay shifts, and independent tasks when claiming broader transfer |
| Continual learning | Retention, interference, adaptation cost, erroneous-update recovery, and state/parameter growth |
| Cost | Wall time, peak memory with measurement scope, stored bytes, bytes read/written where relevant, and acquisition/selection/verification overhead |
| Uncertainty | Multiple independent training seeds; per-seed results and interval method with the actual independent sampling unit |
| Decision | Preregistered useful effect, budget/stop rules, failures, deviations, and retain/revise/reject/inconclusive reasoning |

Do not compute confidence as if correlated tokens, queries from one episode, or checkpoints
from one training run were independent training trials. Preserve per-seed and per-task
results. Define missing-data and failed-run handling in advance. Never drop bad seeds silently.
If a test set informed a design decision, retire it from unbiased final evaluation or label
the reuse and introduce a new held-out set.

## Calibrate learning before testing transfer

An engineering preflight checks numerical behavior, implementation agreement, throughput
and resource admission. It does not show that a task can be learned under that budget.
Use a separate development pilot when informative acquisition has not been established.
The expert comparator is a competent learned baseline with observable learning behavior,
not simply an executable candidate alongside an exact scorer.

Before fitting, register the pilot's task family, observations, supervision, permitted
training conditions, candidate/control choices, data partitions, stage thresholds and
selection rule. Bound total attempts, updates/presentations, compute, elapsed time and
artifact bytes across the whole search, including unsuccessful trials. Specify which
choices may adapt to development evidence and how each choice is logged. A per-run ceiling
alone does not bound a search. Measure throughput to choose an informative admitted scale;
do not silently stretch a budget or treat the first learning rate as an architectural verdict.

For surface-transfer work, use this progression, adapting the details to the chosen task:

| Stage | Observation and decision |
| --- | --- |
| Tiny-set fitting | Try a small noiseless development set, for example 32–64 examples, with both the candidate and a credible baseline. Record training loss and accuracy. Failure localizes optimization, input ambiguity or capacity issues; fitting alone proves no generalization. |
| One-format generalization | Train in one simple format and evaluate fresh development instances in that format. Separate failure to fit from overfitting and successful acquisition. |
| Mixed-format acquisition | Add familiar encodings and report each format separately. Test encoding interference; an aggregate must not hide an unlearned format. |
| Unfamiliar transformations | Only after acquisition, measure development transfer to unused combinations or transformations. This diagnoses the transfer boundary; it is still model-selection evidence. |

Declare numeric gates, minimum per-seed/per-format performance, seed count and failure handling
in the pilot, with thresholds appropriate to the task's chance or trivial baselines. Do not
recycle EXP-0004's 70% floor as a universal standard. Retain all attempts and training curves,
fixed train/validation measurement points, class/support counts, actual presentations and
per-format accuracy. Minibatch loss cannot substitute for measured training accuracy.
Enforce advancement at the declared unit; an individually passing seed does not admit
transformation evaluation for an arm whose required seed group has not passed.
More updates are one possible diagnostic; eight average presentations per example alone
cannot diagnose undertraining.

If a baseline acquires the task but a candidate does not, record that configuration's
acquisition limitation. If neither acquires it by the admitted search limit or registered
early stop, close with a calibration failure. Neither
outcome settles a broad representation hypothesis. A competent baseline may support a later
selected experiment even when this candidate fails. No failed gate permits indefinite tuning.

After development, commit a confirmatory protocol and implementation with selected settings,
fresh confirmation seeds, checkpoint selection, comparison margins, missing-run handling and
cost rules frozen before final evaluation. Reserve final partitions from every development
choice, including auxiliary objectives, ablations and probes. Split at the latent problem or
trajectory level before making multiple views; verify actual-input overlap too. Fresh random
seeds alone do not establish new structures. Retire any inspected final examples and do not
reuse EXP-0004's final data as unbiased evidence. If confirmation misses its acquisition gate,
report that outcome without tuning on the final scores.

## Supervision, representations and useful computation

Specify separately what the learner observes, what supervision it receives during fitting,
and what the scorer alone knows. Masked-input prediction, prediction of observed changes,
paired views from known transformations and own-trained target encoders are permitted.
Disclose the transformation knowledge, targets and training provenance, give controls equivalent
information and tuning opportunity, and charge extra examples, auxiliary networks and updates.
An exact simulator can generate experience and score outputs; it must not silently solve a
candidate's runtime query. A richer training signal is not evidence that the model discovered
the supplied structure unaided.

When compression may discard useful information, compare a raw-input path and a less
restrictive intermediate on fresh development data within the admitted search. Record changes
in solver capacity, access, construction and execution cost. Measure intermediate variation
and ability to support registered task-relevant readouts or interventions. Train any probe
only on permitted data and report its capacity; a failed weak probe is not proof that no
information remains. Entropy, rank, diversity or input reconstruction alone cannot establish
task sufficiency or useful causal dependence.

For a later predictive-state experiment, distinguish observed one-step predictions from
multi-step rollout without intermediate observations. Compare a direct predictor and shared
learned transitions under the same experience and charged repeated work. Begin with fixed
execution budgets; learned halting needs prior evidence that additional computation helps.
For procedure consolidation, distinguish answer caching from new-binding/composition transfer
and measure cumulative cost including discovery, validation, storage, selection and failed
promotions. The claimed benefit must repay acquisition on an explicitly measured workload.

## Preserve fitting evidence independently of verification

New learning workers must write bounded periodic fitting telemetry and atomically publish the
completed fitting record before native evaluation, diagnostics or persistence checks begin.
Include source/protocol/data identities, arm and seed, completed updates, losses, training and
validation metrics, checkpoint identities, selection and measured fitting time. Keep three
outcomes independently visible: fitting completion, verification completion, and resource
admission/final accounting. Missing final measurements are unknown, not zero. Overall success
requires all registered checks and admissions; a completed fit cannot upgrade an interrupted
verification or resource-refused run.

Exercise that boundary by injecting a failure after fitting and confirming that telemetry
survives while verification remains failed or interrupted. A later audit must identify which
saved facts it verified; it cannot invent historical telemetry or repair the run's status.
The existing representation worker writes its final report only after downstream checks;
this revised contract is an N-007 implementation requirement, not an implemented repair.
Parameter snapshots, exact training-resume state, and restored inference state have distinct
proof requirements in [storage and retention](storage.md).

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
