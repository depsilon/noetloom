# EXP-0007 — Learned state representation for reusable transitions

Status: selected design brief for N-011; no fitting admitted until an executable protocol,
implementation, numeric search limits and resource admission have been reviewed and committed.

## Question

Does the compositional behavior observed in [EXP-0006](../EXP-0006/design.md) survive when
observation-to-state encoding and state-to-observation decoding must be learned? The
[preceding decision](../../docs/decisions/0010-learned-transition-pilot.md) found perfect finite
development transfer for a strongly aligned transition bank, while a recurrent sequence
predictor fitted training sequences but failed to generalize to fresh short inputs. That
result leaves representation alignment, transition factorization and learning dynamics
confounded. It does not establish hidden-state drift or insufficient optimizer duration as
the cause.

This study connects H-003's reuse question to a bounded part of H-011: learning a state
representation suitable for repeated computation. The candidate is a limited component
probe. Learned encoders, decoders, action-conditioned dynamics and auxiliary predictive losses
are established research ingredients; their combination is not an originality claim or an
adoption as Noetloom's foundation. Persistent selective memory, learned routing, variable
halting, procedure promotion and language remain separate requirements.

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

The principal controls must separate two questions: the effect of learning the state mapping,
and the effect of constraining recurrent computation to use that state. Include an otherwise
matched latent path with and without the proposed state-consistency objective, and a competent
direct recurrent reference with equivalent access to prefix observations and auxiliary targets.
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

Use the [source catalog](../../docs/research/sources.json) as the starting point for primary
method review, especially R-NAR, R-DREAMERV3 and R-IJEPA. Revisit the actual relevant methods
before selecting a loss, control or architecture; their recorded claims do not validate this
experiment. No new external method is treated as read merely because it is listed here.

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

Only a competent baseline admits a separately registered confirmation with fresh training
seeds and independently reserved final data. Candidate acquisition failure can remain a
scoped result. Freeze effects, uncertainty units, failure handling and decision thresholds
before accessing that final partition. Three seeds in one finite world are development
evidence, not a substitute for independent confirmation or cross-domain generality.

Retain fitting telemetry before verification, parameter snapshots and independent numerical
checks. Replay full prediction/selection results and saved learned state; verify a private
second copy and representative recovery using the existing resource-bounded tooling. Preserve
the original records and include prior-stage, failed-search and recovery costs.

## Stop and interpretation

The executable protocol must set whole-study and per-attempt time, memory, update, example,
prefix-output and storage limits before learning. This brief itself authorizes no run. A
failed acquisition gate closes that trial and identifies the next evidence-supported revision;
it does not justify an unbounded duration or loss sweep.

If learned state mappings preserve composition, retain that mechanism only within the tested
domain and supplied supervision. If only the observation-aligned reference works, retain the
alignment dependence as a measured limitation. If matched controls explain the result,
do not claim an advantage from the candidate mechanism. Neither outcome establishes novel
cognitive primitives, continual learning, a complete foundation architecture or an LLM substitute.
