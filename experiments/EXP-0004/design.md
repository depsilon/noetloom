# EXP-0004 — Can learned organization transfer across surfaces?

Registered for N-006 on 2026-09-30 before implementation or fitting. This is one bounded
H-011 component test. H-001/H-002 remain dormant; no retrieval or allocation optimization
is included. A useful result can motivate a later reusable-computation experiment, but does
not authorize it. The [charter](../../docs/charter.md) still owns the architectural boundary.

## Question, role, and prior art

Does an input-dependent reorganization of a raw numeric field improve relational transfer
to held-out surface transformations, beyond fixed-layout computation of equal or greater
capacity and a learned static reorganization? The intermediate state contains no named
objects, cognitive primitives, instructions, or supplied canonical solution.

[Spatial Transformer Networks](https://arxiv.org/html/1506.02025v3), sections 3–3.4, describes
input-conditioned transformations and differentiable sampling before downstream computation.
[Slot Attention](https://proceedings.neurips.cc/paper_files/paper/2020/file/8511df98c02ab60aea1b2356c013bc0f-Paper.pdf),
sections 2–2.3 and 4–4.1, supplies related learned grouping and a warning that grouping capacity,
training, and supervision must be explicit. This experiment uses dense conditional transport,
not either complete architecture, a Transformer foundation, or an originality claim.

The raw input is still a designer-supplied 8×8 scalar field; the candidate's intermediate
is still sixteen scalars. All learned networks acquire hidden features. The tested distinction
is **input-dependent organization at the solver boundary**, not representation learning versus
no representation learning. Passing would not establish arbitrary ontology discovery,
semantic multimodality, a non-token foundation, interpretable latent states, or LLM substitution.
In particular, the construction network could encode answer-relevant information in transport
weights; the controls and intervention test useful dependence, not semantic disentanglement.

## Problem and observation boundary

A latent problem is a total order of five anonymous entities and an ordered pair of distinct
entities. The binary answer is whether the first precedes the second. The scorer computes
this from the latent order and independently decodes the actual rendered field to check it.
No exact decoder, order, entity list, surface identifier, transform identifier, label, or
cross-surface equivalence pair is available to a learned forward pass.

Each problem is rendered once during fitting in one of three grammars:

- **Numeric ranks:** rows 0–4 contain the respective entity's scalar in column 0. Five
  sorted values are drawn from disjoint intervals centered at −0.8, −0.4, 0, 0.4, 0.8
  with uniform ±0.08 jitter; their row assignment encodes the order.
- **Sequence:** the upper 5×5 block is a permutation matrix: row is sequence position,
  column is entity identity. No rank scalars or pairwise relation table is supplied.
- **Relations:** the upper 5×5 block contains +1 for a preceding row entity, −1 for a
  following row entity, and zero on the diagonal. No sequence or numeric ranks are supplied.

All grammars place +1 and −1 query marks in row 5 at the two entity columns. Unused cells
are zero. Orientation fiducials at (7,7)=2, (7,6)=1.5 and (6,7)=−1.5 make rotations and
reflections identifiable without guessing a hidden coordinate convention. Rotate the whole
field in quarter turns, optionally reflecting columns first. These are sensor conventions,
not cognitive categories. Every arm receives exactly the same flattened 64 values.

Draw distinct latent problems from the 120 permutations ×20 ordered queries. With generator
seed 731991, allocate 768 training, 96 validation, 32 development, four groups of 96 final
problems, and 96 diagnostic problems. Balance labels within each partition, freeze them,
and reject actual rendered-input overlap across partitions. Each training problem appears
in only one surface; neither a paired-view loss nor canonical-representation supervision
is used. Minibatch repeats are ordinary fitting, not new independent evidence.

Seen surface/rotation pairs are ranks {0,1,2}, sequence {1,2,3}, relations {0,2,3}.
Training, validation and development use these pairs without reflection. Final families:
`base` uses seen pairs; `combination` uses ranks 3, sequence 0, relations 1;
`reflection` reflects a seen pair; `joint` reflects a held-out pair. Each family contains
32 examples per grammar. Final problems are disjoint from training, validation, development,
and one another. The final diagnostic group is rendered in all three grammars, using each
grammar's held-out rotation, to measure agreement on previously unseen problems. These views
are never used for updates, checkpoint selection, or redesign within this experiment.

## Four arms and what is learned

All parameters start from project-owned initialization; there are no inherited readers,
pretrained embeddings, teachers, external examples, or hand-written task-solving operators.
Affine layers use independent N(0,1/input_dimension) weights and zero biases, with the
same seed-bound initialization rule in every arm. All hidden activations are tanh.
The solver generator uses the registered seed; construction/static scores use seed XOR
0xC011. Thus C/S start with identical solver parameters. Rendered observations are frozen
as float32 before hashes and independent decoding are computed.

**A / `fixed_small`:** flatten the raw field; apply 64→32→32→2 learned affine layers.
**B / `fixed_large`:** the same fixed layout, with 64→160→160→2 layers. Its trainable
parameter count and nominal forward work must both exceed the complete conditional arm.

**C / `conditional`:** a 64→16→1024 construction network produces a 16×64 matrix of
scores (tanh only after its first layer). Normalize each row with softmax. Multiply that
matrix by the raw 64-vector to create sixteen intermediate scalars. A 16→32→32→2 solver
then predicts the answer. All construction and solver parameters are learned together.
No top-k selection, semantic masks, sparse reads, special surface routing, or exact decoder
is used. All 64 input scalars contribute to the admitted construction path.

**S / `static`:** learn one input-independent 16×64 score matrix, initialized N(0,1/64),
with the same row softmax, transport, and 16→32→32→2 solver. This distinguishes useful
conditional organization from a globally learned projection and low-dimensional bottleneck.

The solver's capacity is fixed within C/S, not its weights. A/B are credible end-to-end
learned controls with unrestricted dense hidden features. These arm definitions are the
whole search space; no extra architectures, temperatures, reconstruction objectives, or
hyperparameter sweeps may be added after scores are inspected.

## Learning budget, selection, and admission

Five seeds: 6101, 6203, 6301, 6407, 6503. Pair data and minibatch indices across arms for
each seed. Use PyTorch 2.14.0 CPU float32, deterministic algorithms and one thread. Adam
learning rate 0.003, betas (0.9,0.999), epsilon 1e−8, no weight decay, norm clipping at 1.
The sole training objective is binary-class cross entropy. Batch size is six.

All arms receive the same selected number of updates, presentations, three validation
opportunities, optimizer rule, and resource ceilings. A development-only preflight chooses
1024 updates, or 512 only if the slowest arm would exceed 60 seconds of extrapolated fitting.
It uses eight warmup and sixteen timed steps, checks gradients and native parity, and never
selects by quality. If neither count fits, stop. Validate at one-quarter, one-half and all
updates; retain the earliest checkpoint with lowest validation cross entropy. There are
exactly twenty arm/seed attempts, including failures, and no seed replacement or retries.

Matched budget means equal learning opportunities and common upper bounds, not fabricated
equality of realized work. Charge actual nominal forward work, a declared training proxy
of three forward counts per presentation plus ten operations per parameter per Adam step,
validation, construction, intervention, replay, startup-inclusive time and process RSS.
The proxy is not a measurement of hardware FLOPs or all optimizer instructions. The larger
fixed baseline is deliberately permitted more realized work than C at the same number of
examples; C may not claim advantage from a greater training budget. Report this asymmetry.
Cap that proxy at 2,000,000,000 operations per fit and each native forward at 100,000.

Shared RunLease, unsynced output, 120 seconds, 32 MiB output, 2 GiB sampled process-group RSS
per preflight, fit or replay; existing bounded Rust tooling and installed Torch only.
No new dependencies or downloads. At 1024 updates a conditional fit presents at most 8,560
cases: 6,144 training +288 validation +768 ordinary final tensor/native +768 intervention
tensor/native +576 diagnostic tensor/native +16 intermediate persistence checks. Other arms
use fewer; all stay below the existing 10,000-case policy. Development data and fixture
checks are separately bounded and cannot inspect final labels. Preserve every initial,
validation and selected checkpoint, immutable executable, raw predictions and failed run.

## Representation intervention and decision

For C, cyclically shift final transport matrices by one example within each family, retaining
each example's raw values and solver weights. Recompute its intermediate state and result.
The shift is fixed before training and uses no correctness information. Charge construction
of all donor maps and intervened inference; it is a causal dependence diagnostic, not a
deployable policy or proof of semantic structure. Report C's matrix variance, entropy,
intermediate values and diagnostic cross-surface prediction agreement. Trace values alone
do not prove that a latent dimension represents a meaningful concept.

Retain this bounded configuration only if every gate passes:

- C mean base accuracy ≥0.85; mean over the three transfer families ≥0.75; each transfer
  family's mean ≥0.70; every seed's transfer mean ≥0.60.
- For each of A, B and S, the paired-seed 95% t interval (df=4) of C minus control on the
  equally weighted transfer families has lower bound >0.05. This conjunction requires
  beating all registered alternatives, without selecting a favorable comparator afterward.
- C minus the shifted-map intervention has paired-seed lower bound >0.03 on transfer.
- Diagnostic all-three-surface prediction agreement ≥0.80. This cannot substitute for
  accuracy or the intervention gate.
- B has at least C's parameter count and declared fitting proxy; all attempts finish within
  admission; all native logits/classes/intermediates agree within 2e−4 absolute tolerance,
  predictions independently replay, and persisted intermediates survive process restart.

Otherwise reject this configuration. If all learned arms remain below 0.70 base accuracy,
also label the representation comparison **inconclusive because task acquisition failed**;
do not call that a falsification of H-011. There is no conditional extension, tuning rescue,
or automatic follow-on experiment. Five training seeds are the independent uncertainty unit.

## Execution and verification boundary

Register a strict `noetloom.representation.v1` protocol and a separate driver. Commit all
protocol and source before the preflight. Numerical fitting lives in the optional Python
backend; Rust performs independent full inference through the existing provider affine
boundary and persists/reopens a constructed intermediate before resuming its learned solver.
This establishes executable representation state, not continual acquisition or a learned
dynamic program. Physical storage formats do not determine the mathematical representation.

Tests must cover all renderers and dihedral transforms, independent decoding, label balance,
actual input isolation, inference rejection of label-bearing fields, exact arm capacities,
resource/protocol/source identity, unknown/invalid parameters, native gradient/parity evidence,
intervention and restart, and replay corruption. Run the full Python/Rust checks, refresh
foundation and EXP-0001 replay evidence after source changes, and finish hosted CI. Keep raw
weights/data local; source and compact evidence use the standing delivery grant. A manifest
is not a durable backup and does not authorize deleting a unique checkpoint.
