# Research program

## Learn a useful system, test one mechanism at a time

The [charter](../charter.md) defines the destination. It does not prescribe a six-box cognitive
architecture or a catalogue of human mental primitives. A plausible starting family is a small
learned controller coupled to selectively read and written state, with bounded recurrent
computation. This is a candidate family to test, not an established Noetloom design.

First build the [Rust foundation slice](foundation-runtime.md): persistent native state,
selective activation, reusable parameterized transforms, and bounded dynamic execution.
The substrate must exist before a meaningful comparison of the proposed system is possible.
Infrastructure fixtures validate this path but do not stand in for a learned candidate.

The first learned experiment should answer whether useful memory access can be learned from
the system's own initialization under a small, matched budget. Begin at the smallest scale
that can distinguish the alternatives after an actual backend and throughput preflight.
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
The immediate learned memory experiment remains scoped; every architecture decision must
state whether it preserves or forecloses these representation questions and why.

## Current direction after the memory probes

The owner selected **N-006 / H-011** on 2026-09-30: one experiment on learning how to
represent a problem across different surfaces. H-001 and H-002 remain open but dormant;
their measured limitations do not authorize another selector, loss sweep, or allocation gate.
The infrastructure is sufficient for this next question. Do not turn maintenance or a
promising ShardLoom analogy into an independent backlog.

[EXP-0004](../../experiments/EXP-0004/design.md) operationalizes one small part of H-011:
an input-conditioned transport constructs an intermediate numeric field before a bounded
solver. Its controls include larger fixed-layout computation and learned static transport.
All networks learn features; “fixed representation” here means fixed organization at the
specified solver boundary, not an absence of learned hidden activations. Neither tensors,
transport, nor the supplied field size become Noetloom's final representation regime.

Reusable computation (H-003) is a possible follow-up if the representation result earns it,
not part of this experiment. H-005 promotion, heterogeneous native formats, non-token units,
cross-representation bridges, and hierarchical physical activation remain open questions.
The owner's landscape percentages are qualitative prioritization, not measured completion
or evidence of capability. Only the plan selects further work.

## From infrastructure to informative learning

EXP-0001 validates the evaluation machinery with hand-written controls. Each episode begins
with empty state. It does not implement persistence across sessions or demonstrate learning.
Its generated development/validation/test splits exercise bookkeeping and capacity shifts;
they do not imply semantic out-of-distribution generalization.

EXP-0002 registered these choices and [rejected its first selective-read configuration](../decisions/0004-learned-selection.md).
EXP-0003 then [rejected the added allocation gate](../decisions/0005-adaptive-allocation.md):
fixed top-one inference over the same dense-trained parameters matched quality with less
logical work. Neither result settles Noetloom's architecture or supports procedural reuse.
Each subsequent learned experiment must resolve them again:

1. **Observation and supervision.** Specify the complete information exposed to each model,
   allowed state writes, loss, update timing, answer format, and reset boundaries. Fit
   preprocessing only on permitted training data. Keep labels and selection metadata out
   of runtime inputs unless they are deliberately shared supervision.
2. **Candidate and controls.** Compare an original memory-access candidate with a credible
   trainable recurrent or small attention baseline and required mechanism ablations.
   A hand-written upper bound diagnoses the task; it is not the principal model baseline.
3. **Budget.** Record backend/version, initialization, trainable parameters, optimizer state,
   memory layout, measured throughput, training/tuning attempts, inference work, disk output,
   and stop conditions. Include warmup and compilation policy. EXP-0002 used an optional
   single-threaded PyTorch CPU trainer and exported parameters to the Rust provider.
4. **Transfer.** Hold out structural changes such as new bindings, longer delays, larger
   working sets, reordered operations, and unseen compositions. Keep training, selection,
   and final evaluation disjoint. Freeze the held-out generator before tuning.
5. **Decision.** Define the smallest useful effect and uncertainty analysis before results.
   Choose retain, revise, or reject based on the complete result, including failures and cost.

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
