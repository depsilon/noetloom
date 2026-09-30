# EXP-0002 — Learned selection over versioned state cells

Registered 2026-09-30, before backend preflight, fitting, or held-out evaluation.
The machine-readable [protocol](protocol.json) fixes the experiment. N-002 owns this work.

## Question and architectural role

Can an own-initialized selector and payload transform learn mutable recall while activating
one payload per query, compared with an equally sized learned dense-read control? This tests
one part of H-001. It does not nominate a final Noetloom architecture. Its fixed-size vectors,
append allocation, event vocabulary, one-step reads, and explicit key descriptors are supplied
scaffolding. Learned allocation, discovered representations, adaptive work graphs, language,
cross-session learning, and general intelligence are outside this claim.

This candidate separates descriptor selection from payload execution. The learned maps are
shared across cells and episodes. Rust performs inference through the execution-provider
boundary; Python/PyTorch supplies automatic differentiation during development only. No
pretrained component, model teacher, external dataset, embedding, or exact-key lookup appears
in the candidate. The scorer alone uses a dictionary to establish expected answers.

Content addressing, differentiable memory, and attention are established mechanisms. The
[NTM methods, sections 3–4.6](https://arxiv.org/html/1410.5401v2) motivated explicit read/write
and reset boundaries; its soft memory heads are not this experiment's exact implementation.
[Zoology, sections 3.2, 4.3 and appendix E](https://arxiv.org/html/2312.04927v1) motivated
multiple query distances and capacity shifts. This is an independently written diagnostic,
not a reproduction of either paper. No novelty or comparison with their reported scores is claimed.

## Learned computation and supplied machinery

Keys are 16 signed bits, values are four categories, and `unknown` is a fifth answer class.
Write input `u` has five coordinates: a value one-hot vector, or the deletion coordinate.
Each write appends one event in a 32-cell ring. Allocation and wraparound are deterministic.
The resident descriptor is `k = Wk key`, with a write counter. The payload is
`v = tanh(E u + e)`, eight floating-point coordinates. Keys are never used as cell addresses.
Deletion appends a learned tombstone encoding, rather than invoking an exact erase routine.
Revisions append new state; choosing the current binding is the learned selector's job.

At a query, `q = Wq key`; each retained event has score
`q dot k / sqrt(8) + a * log(1 + writes_since_event)`. A separate null alternative has
learned score `b` and learned payload `n`. `Wq` and `Wk` are independent, bias-free 8×16
matrices. `E` is 8×5 with an eight-coordinate bias. Answer logits are `O v + o`, where
`O` is 5×8 and `o` has five coordinates. The total is 359 initialized scalars.

Four arms share initialization values, data ordering, parameter shapes, optimizer settings,
checkpoint opportunities, capacity, and time/query ceilings within each training seed:

| Arm | Forward read | Training gradient / intervention |
| --- | --- | --- |
| `selective` | First maximum among null then oldest-to-newest event scores; one payload | Deterministic straight-through softmax: hard forward, soft backward; biased estimator |
| `dense` | Softmax-weighted sum of null and all event payloads | Ordinary differentiable dense attention; principal learned baseline |
| `frozen_routing` | Same hard selection | Freeze Wq, Wk, a, b at initialization; learn payload encoder, null payload, and answer decoder |
| `no_history` | Null payload only | Hide all event descriptors and payloads on query; retain the same parameter allocation and training ceiling |

All tensors begin from the seed's own initialization. Matrix weights use independent normal
draws with standard deviation `1/sqrt(input_width)`; biases, age coefficient, null score,
and null payload start at zero. Only answer cross-entropy supervises fitting. There are no
target addresses, phase labels, correctness signals, or expected answers in runtime inputs.
The straight-through identity follows the standard hard-minus-detached-soft-plus-soft
construction documented by [PyTorch](https://docs.pytorch.org/docs/2.14/generated/torch.nn.functional.gumbel_softmax.html);
this experiment adds no Gumbel noise. Finite-difference checks apply to the dense path;
the hard path's gradient is deliberately not its discontinuous forward derivative.

Training reconstructs each query's causal prefix and computes **all** descriptor and payload
encodings, including the soft backward path. Charge that dense work. Rust inference encodes
each write once, scans every retained descriptor, and then reads the selected payload(s).
Metadata is resident, so sparse payload access does not establish sublinear lookup or low
total memory use. Parameter bytes, descriptors, payloads, staging, nominal arithmetic,
payload reads/writes, observed wall time, and process peak RSS are reported separately.

## Observations, splits, and supervision

Each episode has an empty state, fresh random bindings, and eight queries. The base schedule
writes four distinct keys, queries the first two, writes two distractors, queries the other
two, revises two bindings to different values, deletes a third, then queries both revisions,
the deletion, and a never-written key. Initial order and within-phase query order vary.
Expected answers and diagnostic phase labels are held separately from observable operations.

Training uses 256 fixed episodes. Validation uses 64 base episodes. The four final families
each use 64 episodes: base with unseen keys/bindings; 18 distractors instead of two; 16 initial
bindings instead of four; and an unseen update composition which interleaves queries with
revisions, deletes, and reinsertion. Every family still contains eight scored queries.
The composition family includes retention of an untouched binding, a changed binding,
deletion, reinsertion, and an unknown key. It is not semantic generalization.

Keys are sampled from disjoint deterministic pools: 2,048 training keys, 512 validation keys,
and 2,048 final-evaluation keys from the 65,536 possible bit patterns. The development pool
for timing/gradient checks is disjoint from all three. Seeded generation and input-stream
hashes must verify separation before fitting. The full test generator is frozen in source
before training. No test score selects a checkpoint or changes a hyperparameter.

Queries from the same episode are correlated. The five independently initialized training
seeds are the units for the primary interval: paired seed differences, mean ± t(4, .975)
times sample standard error, with t = 2.7764451052. Show every seed/family and descriptive
episode aggregates; do not count thousands of queries as independent training replications.

## Admission, preflight, and selection

Use PyTorch 2.14.0 CPU float32, one intra-op and one inter-op thread, deterministic algorithms,
and no compilation. PyTorch is an optional development dependency, not a Rust runtime or a
pretrained model. Install only official pinned binary wheels in a dedicated unsynced venv,
with exact package/version/wheel hashes retained. Admission reserves 1 GiB installed tooling
plus 256 MiB download/cache space, retains 20 GiB free-disk headroom, and refuses source builds.
No external training data is downloaded. Checkpoint redistribution remains undecided.

The bounded preflight permits one non-scored development run: import/environment inspection,
dense gradient and Rust parity checks, then 8 warmup and 16 timed optimizer steps per arm.
Do not inspect final-evaluation labels or use preflight quality to choose the method. Select
256 optimizer steps if the slowest measured arm extrapolates below 60 seconds; otherwise
128 if below 60 seconds; otherwise stop and record a backend-budget rejection. Freeze the
selected count before training. Preflight has a 120-second execution deadline and 16 MiB
output ceiling. Dependency setup is separately bounded to 300 seconds and the tooling limits.

Each of 20 arm/seed runs has a 120-second deadline, 16 MiB output ceiling, and at most 10,000
query presentations including validation, both native evaluation and independent tensor parity,
and 16 reserved persistent/restart verification presentations (9,744 at 256 steps). Batch size is 16; Adam uses
learning rate .02, betas (.9, .999), epsilon 1e-8, zero weight decay, and global gradient
norm clipping at 1.0. At 256 steps inspect validation after steps 64, 128, and 256; at 128
steps inspect after 32, 64, and 128. Choose lowest validation cross-entropy, breaking ties
toward the earlier checkpoint. There is one attempt per arm/seed, no learning-rate sweep,
and no failed-seed replacement. Initial and selected weights plus all validation scores
are retained. Train/validation and native final evaluation run serially under one cache lease.

The preflight and every run record source, protocol, environment, inputs, checkpoints,
binary, outputs, resource observations, and failure identities. Compile once in the admitted
Rust tooling cache; compilation/import and data preparation time are visible separately.
The Rust evaluator receives observations and parameter artifacts, never labels. Python
independently checks logits and all predictions against the selected checkpoint, replays
scoring, and tests a checkpoint loaded in a fresh process. Logits must agree within
`3e-5 + 3e-5 * abs(reference)` and predicted classes must match exactly. A bounded persistent-provider
case must survive a separate-process restart with the same learned parameters.

## Decision and stopping rule

Retain the selective mechanism for another experiment only if: mean base accuracy ≥ .90;
mean accuracy across all four families ≥ .85; every family mean ≥ .75; the lower 95% paired
seed interval against dense accuracy is at least −.05; the lower paired interval against
each ablation exceeds .20; and its counted payload-read bytes are at most 25% of dense's.
These thresholds concern this mechanism and this task only. A systems-speed claim additionally
requires observed end-to-end evidence; nominal arithmetic or payload counts alone cannot earn it.

A complete, correctly executed negative result rejects this registered configuration for
progression; it does not disprove learned memory generally. Infrastructure failure, missing
arms, unverified artifacts, or insufficient budget makes the result inconclusive. Do not
increase width, training, tuning, key features, or supervision after seeing results. Record
any necessary correction and whether it retires test data before rerunning. Keep every
failed run and unique checkpoint locally until a separate verified archival decision.

Horizon questions H-006–H-011 remain open. This fixed-vector diagnostic neither establishes
nor forecloses non-token units, multiple representations, or learned problem representation.
N-003 must be selected from the measured limitation after this decision, not from optimism.
