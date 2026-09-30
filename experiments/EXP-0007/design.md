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

The [implementation repair](diagnostics-repair.json) retains the original registration and
failed attempt `transition-diagnostic-run-dc524301a1`. That attempt completed affine fitting
but stopped before comparison scoring because the new reader omitted the historical data's
`rows` envelope. One unused replay allowance becomes a repair run: two runs and two replays
within the same four-attempt, 64 MiB and 480-second ceilings. Science, data, fit and score
definitions are unchanged. The original failure remains a failure.

## Registered representation pilot

The [executable registration](protocol.json) now fixes the experiment below. It must be
committed with its source before any fitting. The completed D1 diagnostic is recorded in
[decision 0011](../../docs/decisions/0011-transition-diagnostics.md): the fitted affine maps
and all six existing one-step/mixed transition checkpoints were correct on all 608 development
trajectories and all 1,920 prefixes. Mixed training added no observed exactness on this set.
Some failed GRU trajectories recovered at their endpoints; that does not establish the cause
of their failure. No further GRU fitting is part of this study.

EXP-0007 uses a fresh ten-bit signed-permutation/flip world. Its 1,024 states are divided into
512 training, 128 validation, 192 development and 192 reserved final states in complement
pairs. Training initial observations and every supervised prefix stay inside the training
partition. Held-out paths may revisit training states, but cannot visit another held-out
partition. The final partition's word structures are audited without rendering trajectories.
The same underlying world and sampling are used for both observation views.

Aligned observations are bipolar coordinates. The nonlinear view is an invertible quadratic
shear: add `1.25*z0*z1` to coordinate 2, `1.25*z3*z4` to coordinate 5, and `1.25*z6*z7` to
coordinate 8, preserving other coordinates. Those products make the observation dynamics
generally non-affine; this is not a dense linear coordinate change or a random lookup table.
Only generation and audit know this mapping. Fitting receives observed vectors and ordered
actions, with observed prefix targets; runtime receives the initial observed vector and
actions. No learner or scorer receives the inverse or canonical-state labels.

The affine reference fits four observed 10-dimensional affine maps from 512 one-step triples.
The two latent arms use the same four affine maps surrounded by learned residual tanh
encoder/decoder networks (10 → 32 → 10), with 1,804 total parameters and a declared identity
initialization bias. The direct control uses four residual observation-space networks
(10 → 64 → 10), totaling 5,416 parameters. Every arm rolls forward from its own predictions.
The direct control has more parameters; report that cost instead of claiming a capacity match.

Both latent arms minimize prefix prediction MSE plus 0.5 times observation reconstruction
MSE. The consistency arm additionally uses unit-weight predicted-state versus encoded-target
MSE, with gradients stopped through that target branch. Encoder weights remain shared and
receive gradients through prediction and reconstruction. Both arms see the same observations;
the consistency arm performs additional computation. Reconstruct initial and every supervised
prefix observation, and gate decoded reconstruction fidelity so a collapsed latent code
cannot qualify merely by lowering consistency error. Equal latent vectors are not required.

Each admitted fit starts from its own initialization, then runs 256 tiny-set, 2,048 one-step
and 2,048 mixed updates in sequence, batch size eight. Passing selected parameters advance
within that fit, using a fresh Adam optimizer at each stage. A failed stage ends the seed.
The two declared rates are 0.003 and 0.01, with seeds 11003, 11009 and 11027. No condition,
duration, width or loss search beyond this envelope is admitted. Nonlinear fitting requires
all three aligned seeds of that arm to pass at one common condition; transfer requires its
own three seeds to pass at one common condition. An arm's progress does not depend on another
arm passing. Select 0.003 before 0.01 when both qualify; compare mechanisms only at a common
acquired condition, otherwise label the result a configuration comparison.

Correctness requires every coordinate within 0.25 of its target at every prefix. Tiny fitting
requires 100% complete-trajectory accuracy. Later gates require 98% training and 95% validation
accuracy, at least 90% in every action/length slice, and 99%/95% training/validation reconstruction
accuracy. Choose minimum validation prediction MSE among qualifying checkpoints (training MSE
for tiny), with earliest step breaking ties. Keep minimum-loss failures as failures. The exact
measurement steps and all data counts are fixed in the protocol.

Development has 608 trajectories across familiar one-step/short, novel-pair, longer-four,
novel-four and longer-six families. Sixty-four additional pairs have different familiar
histories of lengths two and three ending in the same actual development state, followed by
one common unfamiliar suffix. Neither path receives a true-state reset. Score both paths
correct at every suffix step, plus the conditional result when both current readouts are
correct. Report wrong agreement and descriptive state distance separately. Controls remove
initial state, reverse actions, zero state after the history, or explicitly provide the true
current observation as a labeled reset diagnostic. The audit records oracle order sensitivity
by family; unchanged one-step cases cannot support an order-sensitivity claim.

Candidate pilot competence requires at least 95% complete-trajectory accuracy in every
seed/family and 90% both-history suffix accuracy. A useful consistency effect additionally
requires a mean paired increase of at least 0.10 in unconditional continuation accuracy,
no negative seed difference, passing reconstruction and a 0.20 drop after erasing state.
These are development criteria in one world. Confirmation requires a separate registration
with fresh fitting seeds, reserved final data and claim-specific controls before final access.

The study permits at most 36 fits, two preflights, one synthetic failure injection, two affine
fits, 18 transfer evaluations and 86 replays: 145 total attempts, 160,000 gradient updates,
5 million trajectory presentations, 20 million predicted prefixes and 3,072 affine fit
examples including refits. Each attempt permits at most 120 seconds, 2 GiB RSS and 16 MiB
output; aggregate time is 3,600 seconds and retained raw output is 512 MiB, at most 256 MiB
per observation view. Per-run update, presentation, prefix and auxiliary limits are separately
enforced. Failed and recovery attempts count. These are ceilings, not a promise to spend them.

The remainder states interpretation and design constraints behind that registration.

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

The registered learning signals are observation reconstruction and consistency between a predicted
latent state and the encoding of an observed training prefix. These are disclosed auxiliary
signals with charged work. Compare decoded task competence,
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

The representation protocol sets whole-study and per-attempt time, memory, update, example,
prefix-output and storage limits before learning. Its dedicated driver requires committed source
and successful preflight; no final-evaluation operation is admitted. A
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
