# Research program

## Establish competence, then test a mechanism

The [charter](../charter.md) defines the destination. It does not prescribe a six-box cognitive
architecture or a catalogue of human mental primitives. A plausible starting family is a small
learned controller coupled to selectively read and written state, with bounded recurrent
computation. This is a candidate family to test, not an established Noetloom design.

The [Rust foundation slice](foundation-runtime.md) provides persistent native state,
selective activation, reusable parameterized transforms, and bounded dynamic execution.
Infrastructure fixtures validate this path but do not stand in for a learned candidate.
Keep this substrate; further infrastructure needs a measured experimental requirement.

The first learned experiments examined memory access from the system's own initialization.
The current need is a reliably competent learned starting point. Use the smallest scale
that can distinguish alternatives after both an execution preflight and acquisition calibration.
The connected bootstrap machine reports 16 GiB RAM. Earlier 128 GB allocations and
100–300M-parameter suggestions were illustrative and do not govern experiment admission.

Memory, recurrence, adaptive computation, representation learning, and learned program libraries have substantial
prior art. The [source catalog](../research/sources.json) records primary research leads
and what was actually read. Review depth is recorded separately for each entry. Read the
relevant methods, evaluation details, and limitations before implementing a derivative or
claiming a new contribution. Novelty is unassessed.

## Candidate questions

The [hypothesis register](../research/hypotheses.json) contains falsifiable predictions and
falsifiers. It separates immediate **mechanism** candidates H-001 through H-005 from
**foundational representation** horizon questions H-006 through H-011. The first memory
experiments do not define the limits of Noetloom's architecture. The following relationships
explain why the immediate questions matter:

- **State access versus state size.** A compact controller may benefit from a large external
  state only if it can learn what to retrieve, write, revise, or leave untouched. Measure
  wrong writes, missed retrievals, interference, and the full selection cost. Adding a
  perfect dictionary behind a weak learner does not establish learned memory access.
- **Computation versus stored experience.** A recurrent controller may allocate extra work
  to difficult cases or avoid repeating work on familiar structure. Charge routing,
  failed attempts, and halting decisions. Compare at equal training and inference resources,
  not just equal parameter count or a favorable token count.
- **Useful reuse versus brittle shortcuts.** A learned reusable operation must transfer
  across bindings and held-out compositions. A memorized answer table or a manually supplied
  cognitive primitive can score well without acquiring a procedure. Measure acquisition
  cost, selection errors, invalidation, and whether reuse actually reduces end-to-end work.
- **Adaptation versus corruption.** Persistent changes can improve future tasks and also
  destroy old competence. Keep weight learning, episodic writes, temporary activation,
  and promoted reusable structures separately identifiable in experiments. Test retention,
  interference, recovery from erroneous updates, and bounded state growth.

One additional design hypothesis is **reversible acquisition**: uncertain learned proposals
first enter a bounded, versioned working state; promotion into persistent knowledge or
reusable computation is separately tested. This could reduce the cost of mistaken updates,
but selection and verification may cost more than it saves. The system must learn useful
representations and promotion signals; this is not a mandatory hand-coded taxonomy of thought.
Register it as a future controlled comparison rather than implementing it speculatively.

## Representation remains a research object

Protect the charter's north star: “The intelligence is the research object; its architecture
is not yet established.” Memory access is the first diagnostic, not the definition of cognition.
The horizon preserves six questions: units beyond tokens; multiple native representations;
discovered intermediate computation; temporary executable structures; transfer between
representations without a compulsory text bottleneck; and learning how to represent a problem.
Linguistic, relational, spatial, mathematical, procedural, causal, and perceptual information
are examples of desired reach, not a required internal taxonomy.

Horizon entries originate in founder questions, have no claimed research evidence, and do
not authorize experiments. Their predictions and falsifiers are provisional directions for
protocol design. Promotion requires source review, a concrete task and controls, conversion
and representation-learning cost accounting, and an explicit decision in the existing queue.
The completed memory experiments remain scoped; every architecture decision must
state whether it preserves or forecloses these representation questions and why.

## What the first probes established

The owner selected **N-006 / H-011** on 2026-09-30: one experiment on learning how to
represent a problem across different surfaces. H-001 and H-002 remain open but dormant;
their measured limitations do not authorize another selector, loss sweep, or allocation gate.
The infrastructure is sufficient for acquisition calibration. Do not turn maintenance or a
promising ShardLoom analogy into an independent backlog.

[EXP-0004](../../experiments/EXP-0004/design.md) operationalizes one small part of H-011:
an input-conditioned transport constructs an intermediate numeric field before a bounded
solver. Its controls include larger fixed-layout computation and learned static transport.
All networks learn features; “fixed representation” here means fixed organization at the
specified solver boundary, not an absence of learned hidden activations. Neither tensors,
transport, nor the supplied field size become Noetloom's final representation regime.

[The experiment was inconclusive](../decisions/0006-problem-representation.md): every arm
remained below its task-acquisition floor, and one of twenty attempts failed after fitting.
The failed attempt's predictions were separately audited without restoring successful-run
status or repeating optimization. The conditional model's 48.61% transfer accuracy does not
support promotion. H-011 remains open; the result does not discriminate adequately learned
representation strategies or falsify the unrestricted question.

The later course correction selects **N-007: establish an informative learning baseline**.
H-003 can start from a competent original baseline; it does not require conditional transport
or H-011 to win first. H-005 promotion, heterogeneous native formats, non-token units,
cross-representation bridges, and hierarchical physical activation remain open. Earlier
estimates of the fraction of research “exhausted” are withdrawn: no defensible denominator
was defined. Acquisition, transfer, retention, useful recurrence and procedural reuse are
separate milestones. Only the plan selects work.

## N-007: acquisition calibration

N-007 is now [complete with a localized calibration failure](../decisions/0008-calibration-result.md).
All three models learned tiny and single-format problems. A disclosed selection amendment
admitted the strongest control, but only four of five fresh seeds passed mixed-format
acquisition; the fifth lost rank accuracy late in fitting. A reliably competent baseline
has therefore not been confirmed. Retain the learning curves and failure, and require a
separate bounded stability study with fresh final data before the conditional directions below.
The acquisition and artifact-recovery machinery is implemented; the following methodological
requirements remain applicable to future studies.

Follow the [staged development contract](../evaluation.md#calibrate-learning-before-testing-transfer):
tiny-set fitting, fresh one-format generalization, mixed-format acquisition, then unfamiliar
transformations. Register a small development search before running it, with numeric stage
gates and a total attempt/compute/storage budget. Choose task and training conditions using
that development evidence, then freeze a separate final comparison. The first chosen update
count is not a verdict on a broad hypothesis. Preserve all EXP-0004 artifacts and decisions;
new development and final partitions must have explicit separation from prior evaluated data.

A specific diagnostic concerns EXP-0004's 16×64 row-softmax transport. Its solver receives
sixteen input averages with nonnegative weights summing to one per average. In the
[renderer](../../noetloom/representation_data.py), the query markers cancel, the signed
relation block sums to zero, and each sequence matrix contains five ones. With the orientation
markers, whole fields sum to 2 for relations and 7 for sequences, unchanged by rotations
or reflections. Uniform transport therefore cannot distinguish answers within either format.
The conditional weights can still encode information; this calculation does not prove that
the learned representation collapsed, and the raw-input baselines also failed acquisition.

Within the admitted development search, compare a raw-input bypass or a less restrictive
intermediate and measure task-relevant readout performance, intermediate variation and
intervention sensitivity. Charge any capacity and information-access changes. These are
diagnostics of a bottleneck, not an adoption of residual connections or a fixed intermediate
as the Noetloom architecture. State what the measurements can and cannot distinguish.

Allow richer learning signals when they help test the question: masked inputs, observed
changes, or paired training views produced by declared transformations. Disclose them and
give controls equivalent experience. The initial computational vocabulary and architectural
biases must be explicit and tested; the prohibition on a human taxonomy of thought is not
a prohibition on locality, sharing or relational structure.

EXP-0005 implemented the targeted
[fitting-evidence boundary](../evaluation.md#preserve-fitting-evidence-independently-of-verification)
and the owner-selected [second-copy and restore checks](../storage.md#learning-evidence-and-recovery).
Parameter snapshots support inference replay; exact optimizer continuation is a separate,
optional contract. These prerequisites address known recovery gaps without rewriting the runtime.

## Conditional directions after calibration

The following are proposed follow-ons, not additional items in the active queue. Each needs
its own decision and admitted protocol after the preceding evidence is reviewed.

| Proposed direction | Question and decision needed |
| --- | --- |
| N-008: predictive state and compositional execution | Does a shared learned transition retain useful competence on new bindings and action compositions after one-step acquisition? Compare with a direct predictor under equivalent experience and charged repeated computation. |
| N-009: procedure acquisition and consolidation | Can acquired computation transfer to new inputs and repay discovery, checking, storage and selection costs over a measured workload? Compare with repeated execution and answer caching. |

For predictive state, a small simulator supplies observations, actions and consequences during
learning and exact scoring during evaluation. It supplies no hidden reasoning to the learned
runtime. Start with one-step predictions and one observation format. Then train short action
sequences and evaluate new compositions and longer rollouts without intermediate observations;
alternative observation formats can follow established competence. Keep a fixed computation
budget until more iterations demonstrably help. Learned halting is not the first mechanism.

For consolidation, begin with computations that already work. A candidate operation must
produce the recurring effect on new bindings and compositions. Measure acquisition and failed
search, validation, storage, selection, invalidation and subsequent execution together. Report
the observed break-even workload or failure to recover the cost. A previously seen answer
and a reusable operation are different controls. Shared recurrence alone does not establish
procedure discovery, originality or an efficiency gain.

Relevant primary work informs these questions without prescribing Noetloom's architecture:

- [I-JEPA](https://arxiv.org/html/2301.08243v3) predicts target image representations with
  own-trained encoders. Its published method uses Vision Transformers; the predictive objective
  is a research lead, not a requirement to adopt those models or weights.
- [Relational inductive biases](https://arxiv.org/html/1806.01261v3) makes supplied structural
  assumptions explicit. Useful bias and learned computation can coexist; neither guarantees transfer.
- [DreamerV3](https://arxiv.org/html/2301.04104v2) learns action-conditioned latent dynamics
  with observation reconstruction. It is prior art for predictive state in control settings,
  not evidence for Noetloom's language capability or LLM substitution.
- [Neural algorithmic reasoning](https://arxiv.org/html/2105.02761v1) describes learned
  processors and known-algorithm supervision. Such supervision must be disclosed; learned
  execution is not automatically spontaneous algorithm discovery.
- [DreamCoder](https://arxiv.org/html/2006.08381v1) learns program libraries from a supplied
  vocabulary and guided search. Procedure acquisition itself is prior art. A Noetloom
  contribution needs a specific mechanism and comparative evidence.

The [source catalog](../research/sources.json) records the versions and sections actually
read. These are method references, not independent reproductions or adopted implementations.

ShardLoom's retained evidence covers three analytical query shapes on 512 synthetic trace-shaped
rows, without returned certificate payloads or a verified binary-to-checkout binding; see the
[integration decision](../decisions/0003-rust-foundation.md#shardloom-trial-and-decision).
Its next useful role could be analysis of real acquisition curves, failure rates by structure,
and repeated computation. Any such trial must verify its results and total preparation/query
cost. Deeper cognitive-state storage needs a measured workload that justifies it.

Keep a language-facing milestone visible: learn to interpret a constrained instruction,
acquire a new rule from examples, apply it to an unfamiliar composition, and retain that
capability across restart. A hidden hand-coded language interpreter or rule solver cannot
establish this milestone. Success would remain a constrained capability result.

## From infrastructure to informative learning

EXP-0001 validates the evaluation machinery with hand-written controls. Each episode begins
with empty state. It does not implement persistence across sessions or demonstrate learning.
Its generated development/validation/test splits exercise bookkeeping and capacity shifts;
they do not imply semantic out-of-distribution generalization.

EXP-0002 registered these choices and [rejected its first selective-read configuration](../decisions/0004-learned-selection.md).
EXP-0003 then [rejected the added allocation gate](../decisions/0005-adaptive-allocation.md):
fixed top-one inference over the same dense-trained parameters matched quality with less
logical work. Neither result settles Noetloom's architecture or supports procedural reuse.
Each subsequent learned experiment must resolve these choices with acquisition evidence:

1. **Observation and supervision.** Specify the complete information exposed to each model,
   allowed state writes, loss, update timing, answer format, and reset boundaries. Fit
   preprocessing only on permitted training data. Keep labels and selection metadata out
   of runtime inputs unless they are deliberately shared supervision.
2. **Candidate and controls.** Compare the selected own-initialized mechanism with a credible
   learned baseline and required mechanism ablations. A limited probe need not implement the
   entire foundation architecture; state which questions it leaves open.
   A hand-written upper bound diagnoses the task; it is not the principal model baseline.
3. **Budget.** Record backend/version, initialization, trainable parameters, optimizer settings
   and what optimizer state is retained,
   memory layout, measured throughput, training/tuning attempts, inference work, disk output,
   and stop conditions. Include warmup and compilation policy. EXP-0002 used an optional
   single-threaded PyTorch CPU trainer and exported parameters to the Rust provider.
4. **Transfer.** Hold out structural changes such as new bindings, longer delays, larger
   working sets, reordered operations, and unseen compositions. Keep training, selection,
   and final evaluation disjoint. Freeze confirmation generators and settings before final access;
   development transformations and their role in selection must be disclosed.
5. **Decision.** Define the smallest useful effect and uncertainty analysis before results.
   Choose retain, revise, reject or inconclusive based on the complete result, including
   acquisition, failures and cost.

Do not select the backend by popularity or claim a systems win from abstract FLOPs alone.
Inspect current official backend support and measure on the intended hardware. An architecture
that needs a bespoke runtime before it beats a small reference model has a higher evidence burden.

## Generality is a separate evidence ladder

Synthetic recall is a diagnostic instrument. Useful progress next requires learned transfer
and retention under controlled conditions, then independently evaluated tasks spanning
language and code. Multimodal perception, actions, and tools introduce their own data,
environment, safety, and evaluation contracts. Broad LLM substitution needs a maintained
capability profile, credible comparisons, and real task performance at total resource cost.

Do not collapse these levels into a single score. A system may improve memory while degrading
language quality, or reduce inference work while increasing training and state-maintenance
cost. Report that tradeoff directly. An execution trace establishes what ran; its intermediate
representations are not thereby interpretable and its unconstrained outputs are not certified true.

The [plan](../state/plan.json) owns execution order. This document owns research rationale,
not a second backlog or an instruction to run all candidate mechanisms.
