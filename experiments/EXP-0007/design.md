# EXP-0007 — Learned state representation for reusable transitions

Status: active N-011. The separately registered [development diagnostic](diagnostics.json)
admits only its stated evaluations and affine identification after source commitment.
The representation study still requires its own executable protocol, reviewed implementation
and numeric admission before fitting. EXP-0006's frozen campaign and decision remain unchanged.

## Question

Does the compositional behavior observed in [EXP-0006](../EXP-0006/design.md) survive when
observation-to-state encoding and state-to-observation decoding must be learned? The
[preceding decision](../../docs/decisions/0010-learned-transition-pilot.md) found perfect finite
development transfer for a strongly aligned transition bank, while a recurrent sequence
predictor fitted training sequences but failed to generalize to fresh short inputs. That
result leaves representation alignment, transition factorization and learning dynamics
confounded. It does not establish hidden-state drift or insufficient optimizer duration as
the cause.

The review of commit `33da8d2` supplied a stronger competing explanation: four affine maps
fitted to the permitted one-step observations can represent this world exactly. In bipolar
coordinates, each action is a signed permutation. An ordinary affine reference is therefore
necessary; a failed GRU does not establish superiority over competent system identification.
The review reported a standalone 608/608 development result, not a neural-checkpoint rerun.
Its attached external archive was not available locally and has not been inspected.

This study connects H-003's reuse question to a bounded part of H-011: learning a state
representation suitable for repeated computation. The candidate is a limited component
probe. Learned encoders, decoders, action-conditioned dynamics and auxiliary predictive losses
are established research ingredients; their combination is not an originality claim or an
adoption as Noetloom's foundation. Persistent selective memory, learned routing, variable
halting, procedure promotion and language remain separate requirements.

## Existing-artifact diagnostic

EXP-0007-D1 is post-hoc development analysis, separate from EXP-0006. Fit ordinary float64
affine maps on its 640 allowed one-step observations and roll forward continuously without
simulator rules or intermediate answers. Audit every saved prefix from all 24 selected fits
and three development evaluations: exactness by step, first error, later recovery and complete
trajectory correctness. Evaluate the six already acquired one-step/mixed shared-transition
snapshots on the same 608 inspected development cases; reproduce the retained mixed outputs.
No checkpoint selection, GRU sweep, new seed or final access is admitted.

The diagnostic retains exact original manifest/input/checkpoint bytes, new fitted parameters
and full outputs. One run and at most three fresh-process replays share a 64 MiB / 480 second
ceiling; each attempt permits 16 MiB, 120 seconds and 2 GiB peak RSS. Replays repeat and charge
affine fitting. Failed attempts remain charged. This measures what the old training contributed
and whether correct endpoints conceal intermediate failures; it is not independent confirmation.

## Coherent comparison to make executable

Use one fully observed transition domain with a fresh world and fresh partitions, keeping
the observation format and complete ordered action input common to every arm. Begin from
the prior finite domain so the first comparison changes the representation burden. A fresh
world tests a new instance of that domain, not generality beyond its algebra.

Retain an observation-aligned transition reference, and introduce an own-initialized learned
encoder, latent transition and decoder. The latent coordinates must not be declared to equal
observed bits, and runtime must receive no exact inverse encoding, simulator transition,
teacher model or true intermediate state. Repeated predictions evolve from the model's own
state. Dimension, capacity, action conditioning and all provided structural constraints must
be explicit in the protocol.

The principal sequence is an observation-aligned affine transition reference, learned
encoder/decoder around the same action-specific affine transition family and latent width,
then that same learned system with a state-consistency objective. Include a competent direct
observation-space predictor with equivalent access to prefix observations and auxiliary targets.
This separates learning the state mapping from the effect of its proposed auxiliary objective.
Sharing an input/output representation or supervised state target must be declared. Count
parameters, training examples, auxiliary forward passes, gradient work and inference conversions.
Do not compare an advantaged candidate only with the already failed EXP-0006 GRU configuration.

Potential learning signals are observation reconstruction and consistency between a predicted
latent state and the encoding of an observed training prefix. These are candidates for the
registration, not settled losses or free extra information. Compare decoded task competence,
reconstruction of answer-relevant information, and interventions that remove or mismatch the
state signal. Prevent a collapsed representation from satisfying consistency while losing
useful information. Gradients, variance and a low consistency loss alone cannot establish this.
Specify whether target encoders share weights, stop gradients or move over time, and give the
relevant controls the same supervised information and tuning opportunity.

Establish acquisition with the original observation coordinates, then change only observation
encoding to one structured invertible nonlinear mapping. A dense invertible linear coordinate
change preserves affine dynamics and belongs in implementation checks. Do not use an arbitrary
lookup encoding. The nonlinear challenge must preserve full observability while withholding
the inverse and canonical state from the learner; audit all reconstruction targets as well as
initial observations for leakage into reserved state partitions.

Construct distinct histories that reach the same actual environment state, then continue both
learned states through the same unseen suffix without resetting to the true observation.
Score correct agreement at every future step, report agreement when both are wrong separately,
and retain unconditional support alongside a conditional diagnostic when both current
observations are correct. Numerical equality of latent vectors is not required. This is the
behavioral test of reusable state; a small latent consistency loss does not substitute for it.

Use the [source catalog](../../docs/research/sources.json) as the starting point for primary
method review. R-KOOPMAN and R-E2C now record actual methods reads of learned embeddings,
reconstruction/prediction objectives and latent transition consistency. Their continuous-dynamics
and control results do not validate this finite action-domain experiment. R-NAR, R-DREAMERV3
and R-IJEPA provide separately scoped context, not a novelty claim for encoder/transition/decoder
structure.

## Evidence required before a conclusion

Register tiny fitting, one-step generalization and short free-running prediction gates before
unfamiliar compositions. Use a bounded development search with declared initialization seeds,
learning-rate/objective choices, identical comparison durations, measurement fractions and
per-slice checkpoint selection. Choose the smallest informative controlled set rather than a
large architecture sweep. Publish every failed attempt and close the trial at its limits.

Audit all actual model inputs and auxiliary targets for ambiguity, latent/effective overlap
and computation equivalence before fitting. Reserve held-out net computations across every
training prefix and subword relevant to the claim. New encodings or coordinate permutations
cannot count as new computation if the model's symmetry makes them training-equivalent.
Do not inspect or reuse EXP-0006's reserved final trajectories to choose the new setup.

Verify that negative controls actually perturb answer-relevant order within every claimed
composition family; the prior sorted-action oracle left its ascending novel-pair family
unchanged. Record unchanged support and interpret only sensitive comparisons. Separate new
instances, new compositions and longer rollouts in all summaries.

Gate claims separately: candidate competence requires its own acquisition and held-out evidence;
a mechanism effect requires a matched contrast; practical advantage requires competent relevant
alternatives and total costs. An unrelated failed recurrent configuration is not a universal
gatekeeper. A separately registered confirmation needs the prerequisites for its specific claim,
fresh training seeds and independently reserved final data. Candidate acquisition failure can
remain a scoped result. Freeze effects, uncertainty units, failure handling and decision thresholds
before accessing that final partition. Three seeds in one finite world are development
evidence, not a substitute for independent confirmation or cross-domain generality.

Retain fitting telemetry before verification, parameter snapshots and independent numerical
checks. Replay full prediction/selection results and saved learned state; verify a private
second copy and representative recovery using the existing resource-bounded tooling. Preserve
the original records and include prior-stage, failed-search and recovery costs.

## Stop and interpretation

The representation protocol must set whole-study and per-attempt time, memory, update, example,
prefix-output and storage limits before learning. Only D1's stated diagnostic is currently
registered; this brief alone admits no representation fitting. A
failed acquisition gate closes that trial and identifies the next evidence-supported revision;
it does not justify an unbounded duration or loss sweep.

If learned state mappings preserve composition, retain that mechanism only within the tested
domain and supplied supervision. If only the observation-aligned reference works, retain the
alignment dependence as a measured limitation. If matched controls explain the result,
do not claim an advantage from the candidate mechanism. Neither outcome establishes novel
cognitive primitives, continual learning, a complete foundation architecture or an LLM substitute.

Only after this representation comparison is informative should a separate registered study
add input-dependent interactions to the underlying dynamics. Do not change both burdens at
once. Provider rewrites and deeper ShardLoom integration remain outside this item.
