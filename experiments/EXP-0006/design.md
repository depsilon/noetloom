# EXP-0006 — Learned state transitions and unfamiliar compositions

Status: executable bounded development registration for N-008 in [protocol.json](protocol.json).
Final evaluation remains unavailable until a separate reviewed, committed registration. The
[input-validity correction](../../docs/decisions/0009-input-validity-and-next-study.md)
explains why this replaces further polishing of EXP-0005's static classifier.

## Question and candidate role

Can compact, own-initialized transition machinery learn the consequences of actions and
reuse those changes in action sequences not experienced during fitting? The desired
observation is useful composition of acquired computation, with its extra work charged.
This is a limited component probe toward Noetloom's persistent-state foundation, not an
adoption of a familiar recurrent architecture as the foundation itself.

It probes [H-003, learned reusable computation](../../docs/research/hypotheses.json).
H-011's representation-discovery question remains separate and open; the present experiment
supplies observation-aligned coordinates and cannot establish learned representation discovery.

The candidate maintains a learned working state, applies the same action-conditioned
transition parameters repeatedly, and predicts a resulting observation. A credible direct
sequence-to-outcome predictor receives the same starting observation, ordered actions,
supervision and development opportunity. Its variable-length input path must not depend
on untrained positional parameters for longer evaluation sequences. A one-step-only or
action-order-insensitive negative control tests whether composition actually matters.

The simulator generates a small observable state, action, consequence domain. It may define
environmental action semantics; it must not implement the candidate's inference procedure.
The learned path receives all required state and action/query information, without hidden
next-state labels or an exact transition decoder. Entity addresses, local update structure,
action vocabulary, intermediate-state supervision and parameter sharing are supplied biases
when used, and must be declared. They are not a required taxonomy of human reasoning.

The first implementation must choose the smallest domain that admits order-sensitive
compositions and materially different held-out computation. It must exhibit concrete
pairs whose different action orders have different outcomes. New entity bindings alone
cannot carry a structural-transfer claim when the model's equivariance makes them
rearrangements of training experience.

## Development before confirmation

Keep one observation format. Separate three stages: tiny-set fitting, one-step prediction
on fresh effective inputs, then short-sequence prediction without intermediate observations
at inference. Measure exact state accuracy as well as component accuracy so unchanged
state does not hide failed updates. Report changed components, action families and sequence
lengths separately, with class/support counts and trivial-copy controls.

Use at most two declared learning rates with the **same** update count, batch size and
measurement schedule, and three development seeds per condition and compared arm. Fix a
small update count and verify its feasibility with admitted execution throughput before fitting;
the executable protocol must give its numeric value and whole-search ceilings. A checkpoint
can qualify only when every required training/validation slice passes its frozen acquisition
floor. Among qualifying measurements choose the lowest validation loss, then earliest step;
otherwise retain an acquisition failure. Do not pick a successful checkpoint using final data.

Report worst-slice performance, selected-checkpoint variation, learning curves and failures.
The baseline's task-specific acquisition admits a comparison; a candidate's failure to acquire
is itself a scoped comparison outcome, not a reason for indefinite tuning. If no competent
baseline is established within the pilot envelope, localize the limitation and close that
trial before selecting a new bounded revision.

## Make held-out computation real

Before fitting, audit exact observations, latent trajectories, and equivalences induced by
fixed preprocessing or architecture. Specify whether each dataset measures optimization,
new effective instances, new bindings, held-out ordered action combinations, or longer
rollouts. Keep pairs/compositions selected for transfer absent from every training view and
auxiliary target; validate this independently of the learned predictor. Counterexamples
with different targets must stay distinguishable through the actual input path.

Partition complete trajectories before rendering views, and use a fresh task/generator
identity distinct from EXP-0004/0005. Development may inspect its own held-out compositions;
final structure choices and cases must be reserved independently. Five fresh training seeds,
the selected settings, useful effects, uncertainty method and failed-run handling are frozen
in a separate confirmation registration before final access. Record comparisons per family,
not only a global average.

Start with a fixed action-conditioned execution budget. At evaluation, roll forward from
the initial observation with no intermediate simulator access. Charge repeated transitions,
direct-predictor work, training presentations, verification and storage. Test restart of the
candidate's saved learned state where applicable; do not count the existing Rust fixture as
learned persistence. Learned halting, procedure promotion, new storage providers and language
are later questions that need evidence for their own admission.

## Protocol completion boundary

Before any fitting, register and validate: concrete domain and source version; complete input
and supervision contracts; candidate/control implementations; all split identities and
equivalence audits; numeric acquisition gates; update/attempt/presentation/time/memory/output
ceilings; failure retention, snapshot/replay and backup scope; selection and stop rules.
Use the existing bounded local tooling and recovery machinery. No pretrained weights,
external teacher, paid compute or runtime rewrite is implied.

Read the relevant prior-art methods when choosing the specific implementation.
[Neural algorithmic reasoning](https://arxiv.org/html/2105.02761v1) discusses learned
processors trained with known algorithmic supervision; recurrence and reuse alone are not
novel. Noetloom's contribution must come from a specific learned state/computation mechanism
and measured capability. Keep alternative representations and mechanisms open as the
evidence improves the design.

## Concrete probe and supplied structure

The environment has eight fully observed binary coordinates and four anonymous actions.
Each action is a fixed randomly generated permutation of coordinates followed by an XOR
mask. Thus an action can move or invert information, and actions need not commute. This is
deliberately a tractable transition-acquisition task; it supplies an environmental algebra,
not a human taxonomy of cognition. There is one world, one observation format, and no hidden
query. Claims concern this finite algebra only.

The `shared_transition` probe learns four dense eight-by-eight matrices and four biases
(288 parameters). An action selects its matrix; the current eight probabilities are scaled
to [-1, 1], mapped to logits, and passed through sigmoid for the next working state. It receives
no exact permutation, mask, or simulator access. State coordinates aligned with observations,
action factorization, and shared transition parameters are strong supplied biases, especially
well matched to this environment. Selection by the supplied action is fixed routing, not learned
selective activation. This probe does not settle the foundation's representation problem.

The `direct` control maps the initial eight bits into a 64-dimensional hidden state, consumes
one-hot actions through a GRUCell, and predicts eight outcome logits after each action
(14,536 parameters). It has learned initialization and decoding, shared recurrent weights,
and no new position-specific parameters at longer lengths. Both arms recur. This comparison
concerns explicit observed-state reuse versus a dense history representation, not recurrence
versus its absence. The implementation follows the published
[PyTorch 2.14 equations](https://docs.pytorch.org/docs/2.14/generated/torch.nn.GRUCell.html);
an independent scalar implementation checks both logits and native states.

Every training trajectory supplies all prefix outcome bits to **both** losses. Models run
from their own preceding state, without teacher forcing or true intermediate observations.
This extensive simulator supervision is disclosed assistance. Binary cross-entropy averages
over bits and prefixes within each trajectory; same-length minibatches are sampled with length
probability proportional to the training-set counts. Both arms see the same minibatch schedule
for a seed. Each stage starts from scratch, so earlier stages establish viability rather than
providing undisclosed additional warm-start experience.

## Partition and input validity

Complementary initial-state pairs yield 160 training, 32 validation, 32 development-transfer
and 32 final initial states, with every bit balanced in each split. Tiny fitting uses eight
training states times four actions (32 cases). One-step training uses all 640 training and
128 validation cases. Mixed fitting adds 128 training and 64 validation trajectories at each
of lengths two and three: 896 training and 256 validation cases in total.

Training and every auxiliary prefix exclude ordered pairs (0,1), (2,3), (1,0), and (3,2).
The first two pairs belong to development transfer and the latter two to final transfer.
The six transfer families are fresh one-step inputs, fresh short inputs using familiar words,
novel pairs, unfamiliar four-step compositions of familiar pairs, four-step words with novel
pairs, and unfamiliar six-step compositions of familiar pairs. Counts are 128, 128, 64, 96,
96 and 96 trajectories respectively. Same/short families measure new effective instances;
the other families measure held-out computations and/or longer rollouts.

Canonical signed-permutation signatures reject a transfer word if its net computation equals
any allowed training word of length one through three, including auxiliary prefixes. The
longer families reserve alternating four-action words. Every four-action window of a development
six-step word must belong to the development pool. Final net computations also exclude
**every contiguous subword** of every eligible development-transfer word. This is stronger
than checking only sampled examples or supervised prefixes. The structurally admitted word
counts are 2, 54, 56 and 150 for development, and 2, 54, 56 and 486 for final transfer.
These counts may be audited before fitting; final starting-state/target trajectories are not
rendered. Evaluation signatures never enter learned forward inference.

The model input audit expands training, validation and development trajectories into every
supervised prefix, tests contradictory labels and cross-split input collisions, and checks
complete latent-trajectory overlap. It tests all six unordered action pairs for order-sensitive
counterexamples. Neither forward path sorts, pools or truncates inputs. A finite collision-free
audit does not establish unlimited observability or learned ability. Initial-state separation
does not forbid intermediate training targets from taking a value used as a held-out initial
state; learned local-transition reuse is the intended mechanism, not a withheld local-rule claim.

## Acquisition, selection and cost

Fixed stage durations are 256, 1,024 and 2,048 updates, batch size 16. Execution preflight uses
independent random labels and must project the largest duration below 70 seconds before any
task fitting; the 120-second worker ceiling leaves evaluation/replay margin. Failure of this
throughput condition closes admission rather than extending runtime. Learning rates 0.003 and
0.01 have identical duration and measurement fractions (0, 1/8, 1/4, 1/2, 1). The second rate is
tried only if all three seeds did not acquire under the first. An arm advances only after all
three seeds pass its preceding stage. This gives at most 36 development fits and two preflights.

Every action and sequence-length slice must pass: tiny training exact accuracy 0.95;
one-step training/validation 0.90; mixed training 0.90 and validation 0.85. All these slices
also need at least 0.95 changed-bit accuracy relative to the initial state, with nonempty
support. Final-state exactness prevents unchanged coordinates from hiding errors. Prefix
loss and final accuracy serve different purposes and are reported separately. Select lowest
validation loss among measurements passing **all** slices (training loss for tiny), breaking
ties at the earliest step. If none passes, retain the failed gate and a diagnostic minimum-loss
snapshot. Loss alone can never admit an arm or a transfer run.

Three-seed mixed acquisition admits separate development transfer and its untrained, copy,
sorted-action exact-oracle and reversed-action controls. The oracle is explicitly labeled and
does not count as a learned baseline. A five-seed confirmation may be implemented and registered
only after the direct baseline qualifies; this development driver cannot access final data.
Candidate acquisition failure remains an informative scoped outcome. No final cases are used
to choose rates, update duration, snapshots or architecture.

Each fit retains losses, batch lengths, all measurement parameter snapshots, final selected
weights, observed inputs/targets, predictions, resource usage and source hashes. Completed
fit records are atomically published before verification; one injected downstream failure
tests preservation. Fresh-process replay regenerates inputs, recomputes every fitted measurement,
checks selection and predictions, and resumes serialized native state for available lengths.
Snapshots lack optimizer state and are not exact training-resume checkpoints. Pure-Python
equations sample twelve trajectories; full tensor replay shares the numerical library.

The protocol caps the whole search at 70,000 updates, three million trajectory presentations,
ten million prefix outputs, 12,000 supervised worker seconds and 768 MiB of artifacts. Each
worker gets 50,000 trajectory presentations, 180,000 prefix outputs, 120 seconds, 2 GiB RSS
and 16 MiB output. Replays, failures, controls and preflight remain charged. Scalar multiply
and add count separately, nonlinear calls count as one; backward is estimated at twice forward
and Adam at ten operations per parameter per update. These proxies are not measured FLOPs;
wall time, high-water RSS and actual bytes are reported alongside them. Dataset construction
and exact-control generator arithmetic are not learned inference work. Runs share the existing
serialized unsynced cache. Prior N-007 bytes must match the verified owner-selected private
backup before fitting. New evidence uses the same private local retention choice, including
byte-verified restore and representative inference replay; same-disk copying does not protect
against loss of the disk. No raw data or weights enter Git.
