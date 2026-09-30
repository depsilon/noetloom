# EXP-0006 design brief — Learned state transitions and unfamiliar compositions

Status: selected direction for N-008; not an executable learning registration. The
[input-validity correction](../../docs/decisions/0009-input-validity-and-next-study.md)
explains why this replaces further polishing of EXP-0005's static classifier.

## Question and candidate role

Can compact, own-initialized transition machinery learn the consequences of actions and
reuse those changes in action sequences not experienced during fitting? The desired
observation is useful composition of acquired computation, with its extra work charged.
This is a limited component probe toward Noetloom's persistent-state foundation, not an
adoption of a familiar recurrent architecture as the foundation itself.

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
measurement schedule, and three development seeds per condition and compared arm. Choose
the smallest informative update count from admitted execution throughput before fitting;
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
