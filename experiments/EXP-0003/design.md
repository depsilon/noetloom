# EXP-0003 — A learned decision to continue reading

Registered on 2026-09-30, before implementation and final evaluation. This is a bounded
compute-allocation probe for N-003, motivated by [EXP-0002's negative selection result](../../docs/decisions/0004-learned-selection.md).
It does not revise that result, establish the Noetloom architecture, or test procedural reuse.
The [charter](../../docs/charter.md) and its representation horizon remain unchanged.

## Question and prior art

Can a small learned gate retain the quality of a frozen dense reader while reducing reads
and total nominal inference work on new bindings and operation structures? The gate may
continue after a first payload read; it cannot invent an answer, perform exact-key lookup,
or inspect the scorer. A successful test would support this allocation component only.

[ACT](https://arxiv.org/html/1603.08983v6), sections 2–2.2 and the experimental setup in
section 3, motivates charging the halting decision and defining the cost/error tradeoff.
ACT uses shared recurrent transitions, cumulative halting weights and a ponder penalty;
its cost coefficient is sensitive and its experiments search it extensively. This probe
uses a two-stage supervised allocation rule, not ACT's recurrence or gradient estimator.
There is one fixed cost coefficient, no hyperparameter search, and no novelty claim.

## Inherited component and roles

Freeze all five EXP-0002 dense checkpoints, including every seed: 1103, 2207, 3301, 4409,
5519. Their 359 fitted scalars were initialized and trained by this project; they are not
externally pretrained components. The parent experiment's own validation selected them.
Do not select parents by test performance, refit them, or substitute the hard-selection
checkpoints. A committed parent inventory will bind run, manifest, parameter hash and step.
Inherited training and checkpoint-selection costs remain visible and common to all arms.

Each frozen reader has the existing 32-event ring plus null payload, learned key/query
projections, learned payload encoder/decoder, and age term. Ring allocation, event vocabulary,
signed-bit keys, and feature formulas are supplied experimental structure. Only a new
seven-scalar linear gate is fitted. The probe preserves possibilities for later representations;
it provides no evidence that these supplied structures are the right cognitive foundation.

## Inference and controls

The learned policy computes routing scores from all resident descriptors and reads the
highest-scoring payload. It applies the frozen decoder, then forms six features:

1. The highest routing softmax probability.
2. The highest minus second-highest routing probability (second is zero for one cell).
3. Routing entropy divided by log(max(2, number of available cells including null)).
4. The highest softmax probability of the five first-read output logits.
5. The highest minus second-highest output probability.
6. Occupied non-null cells divided by 32.

All features are observable before additional payloads are read. The gate continues iff
its linear score is nonnegative. Continuing reads each remaining payload once, reuses the
first read, forms the frozen dense weighted average and applies the same decoder again.
Halting returns the first decoder result. There are at most two decoding stages. Labels,
query phase, split identity and dense results are not gate features. No state is changed by
a query. Writes/deletions follow the existing versioned event path; parameters stay frozen.

The native fixed `top_one` and fixed `dense` controls use exactly the same inherited weights
and observations. They bypass the learned gate. Their quality/cost endpoints also define
an input-independent random allocator: within each held-out family choose dense with fixed
probability r, where r makes its expected payload bytes equal the learned policy's measured
bytes. Expected accuracy is (1-r) times top-one accuracy plus r times dense accuracy. This
is an analytical control using both measured endpoints, not a third deployed implementation
or timing observation. r uses only aggregate byte counts, not correctness. Allowing a separate
r for each family makes the comparison conservative but does not establish a deployable
family classifier. Report per-family r and the formula; do not silently optimize endpoints.

Inherited fitting is matched; the gate adds seven parameters and its explicitly charged
acquisition budget. Controls need no additional fitting. This tests whether that bounded
extra acquisition buys useful allocation, not equal-parameter end-to-end training superiority.

## Fresh data and held-out structures

Exclude all 5,120 keys in EXP-0002's complete train/validation/test/development pools.
Shuffle the remaining sixteen-bit keys with seed 981733. Allocate disjoint pools of 1,024
training, 256 validation, 2,048 test and 128 development keys. Preserve input-stream hashes
and independently recompute expected answers with an exact reference used only by the scorer.

Generate 64 base training episodes, 32 base validation episodes, and 32 episodes in each
of four test families, with eight queries each. Test families are base (new bindings), delay
(18 distractors), capacity (28 initial bindings), and interleaved (the new sequence below).
Base/delay reuse the documented event semantics from EXP-0002 with new keys and generator
seeds. Capacity uses the base sequence with 28 initial bindings; query targets remain within
the 32-event capacity when needed. The interleaved sequence starts with four writes and
two initial queries, deletes key 0, revises key 1, queries key 0's deletion, reinserts key 0,
queries key 1's revision, adds two distractors, queries key 0's reinsertion, deletes key 1,
queries that deletion, restores key 1's original value, queries its recovery, then queries
an unseen key. This yields eight queries and is absent from gate train/validation.

The test examples and interleaving are frozen before learning. EXP-0002's observed scores
informed this hypothesis, so its examples are retired from unbiased evaluation here.
This remains synthetic structural transfer, not language or semantic generalization.
Old event payloads remain present after revisions/deletions, testing stale-state interference.
There is no procedure cache; learned-procedure acquisition and invalidation are untested.

## Fitting and selection

For each parent seed initialize six gate weights independently from N(0, 0.1), with that
seed XOR 0xACE3; bias starts at zero. PyTorch 2.14.0 CPU float32, one thread and deterministic
algorithms, as already installed for EXP-0002. Fit only the gate using Adam, learning rate
0.02, betas (0.9, 0.999), epsilon 1e-8, no weight decay and gradient norm clipping at 1.
No dropout, teacher, model-generated labels, or external data is used.

On training observations, precompute both frozen branch outputs and the six features.
This accesses all payloads during acquisition and is charged separately from sparse
deployment. Let es and ed be zero/one errors of top-one and dense, m the available cell
count, and p the sigmoid of the gate score. Minimize the batch mean of

`(1-p)*es + p*ed + 0.02*(1 + p*(m-1))/m`.

Errors and features are constants for gate fitting. This is expected randomized-policy
utility; deployment thresholds at zero, a declared objective/deployment mismatch checked
by deterministic validation. Use minibatches of eight sampled with replacement from the
512 training queries by a seed-bound RNG. This is no longer the biased hard-selection
backward pass of EXP-0002.

One bounded development preflight times eight warmup and sixteen fitting steps, checks
numerical gradients, and compares independently implemented tensor/native branches and
gate features. It chooses 128 steps, or 64 only if 128 exceeds the 30-second extrapolated
fitting allowance. Reject if neither fits. Do not inspect quality to choose the step count.
Use separate development keys and preserve the preflight artifacts.

Validate at one-quarter, one-half and all selected steps. Select the earliest checkpoint
with lowest deterministic validation error plus 0.02 times mean per-query payload fraction.
There is no threshold search, cost sweep, seed replacement, or final-test selection. Preserve
initial, all validation and selected gate weights. All five seeds are independent inherited
training trials paired across policies; queries are not independent training trials.

## Resource admission and cost accounting

Use the existing shared local lease and unsynced caches. Each preflight, seed run, replay
and summary reserves 16 MiB with a 120-second wall limit and 2 GiB observed process-group
RSS ceiling. The parent monitors worker output, wall time and RSS; final OS high-water RSS
is checked. Sampling is not an OS memory sandbox. No new dependencies or network downloads.
Compilation uses the existing bounded Rust tooling directory and two-job cap.

At the maximum 128 steps, each seed run admits at most 9,488 query presentations: 1,024
training branch outputs, 1,024 gate minibatch queries, 512 validation branch outputs, 768
validation gate queries, 3,072 final tensor policy outputs, 3,072 final native policy outputs,
and 16 queries for a separate-process adaptive persistence restart. Cached feature calculation
shares branch results and is included in elapsed acquisition time. Replay is a separate
admitted run of 3,072 native predictions. The global 10,000-case per-run ceiling stays intact.
Preflight uses only eight development episodes and is below the same ceiling. There are five
seed attempts; failures remain evidence and prevent a retain decision. No automatic retries.

Record parent training manifests, gate fitting and branch-preparation wall time, actual
nominal native operations (including feature construction, gating and the first decoder
on continued queries), descriptor reads/validation, payload reads/writes, continuation count,
stored bytes, process startup-inclusive native time and internal time. Null initialization is
separate. One timing observation per policy/seed is descriptive, not a speed benchmark.
Do not equate a payload reduction with lower total memory, sublinear routing, or latency.

## Registered decision

Retain this allocation configuration only if **all** gates pass across the complete five seeds:

- Mean accuracy at least 0.80 and minimum family mean at least 0.70.
- Paired-seed 95% t interval (df=4) for adaptive-minus-dense accuracy has lower bound at
  least -0.02, and each family's mean loss versus dense is at most 0.03.
- Paired-seed 95% t interval versus the equal-payload analytical random allocator has lower
  bound above 0.005. This requires useful input dependence, not just inherited quality.
- Aggregate payload bytes are at most half of dense, and total nominal scalar operations
  are no greater than dense, charging event processing as well as query work.
- Each seed continues on at least 5% and at most 95% of final queries.
- All native/tensor decisions, classes and logits agree within the frozen numerical tolerance,
  all final predictions replay, all resource limits hold, and all five attempts complete.

Otherwise reject the registered configuration; preserve endpoint results and the reason.
An always-halt result can motivate a simpler fixed policy but does not count as adaptive
success. No broader mechanism, recurrence, or procedural-reuse conclusion follows.

## Verification registered before implementation

Implement a strict `noetloom.allocation.v1` protocol and separate `scripts/allocation.py`
driver. Required commands are `python3 -B -m unittest discover -s tests -v`,
`python3 -B scripts/rust.py check`, `python3 -B scripts/rust.py fixture`,
`python3 -B -m noetloom check`, and a fresh EXP-0001 run/replay after source changes.
The learning workflow is `python3 -B scripts/allocation.py preflight`, then
`python3 -B scripts/allocation.py campaign --admission PATH`; `verify --run PATH` performs
independent native replay. Commit the exact protocol and implementation before preflight.
Test malformed gate artifacts, no label-bearing runtime inputs, both branches, reuse of
the first payload, deterministic ties, source/parent identity, replay corruption, output
admission and split separation. Compare numerical gradients on the smooth training loss.

Use the existing persistent provider for prefix/restart in separate processes, and the
resident provider for full evaluation. Keep all unique parent/gate checkpoints local;
record exact hashes and locations before any future archival or retirement. Compact source
and evidence can be delivered under the standing grant; raw weights/data are not published.
