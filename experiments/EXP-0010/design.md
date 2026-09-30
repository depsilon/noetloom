# EXP-0010 — Retain operations through an observation change

[Decision 0014](../../docs/decisions/0014-affine-coordinate-acquisition.md) establishes
nonlinear acquisition and decoded composition in three EXP-0009 seeds. This separately
registered development study asks whether those learned operation coefficients remain
useful when the same world is observed differently. It is a component reuse experiment,
not a test of a new foundation, new dynamics or general continual learning.

## Fixed task and four controls

Keep the original dynamics, partitions, observed training consequences and 1,780-parameter
reversible model. Each of three adaptation seeds is bound to its own successful parent;
the exact parent manifests, snapshots and competence evaluations are in the
[protocol](protocol.json). No parent is chosen after inspecting adaptation quality.

Cross two factors: mapping initialization (retained or newly initialized) and operation
treatment (frozen at the acquired values or refitted from the new observations). The four
arms are `frozen_warm`, `frozen_reset`, `refit_warm` and `refit_reset`. All optimize only
the 1,340 coupling parameters with Adam. Refit arms use the unchanged EXP-0009 detached
affine solver, data support and 32-update schedule. The reset/refit arm is the relevant
from-scratch comparator, with its own acquisition opportunity in each new view.

This factorial comparison separates operation reuse from a favorable mapping initialization.
Within each mapping initialization, the difference is retaining old affine coefficients
versus recomputing them. Refit uses extra observations of the same training pool and solver
work; that intervention and cost difference are explicit. The inherited learned weights
are Noetloom's own outputs, not externally pretrained teachers.

## Two observation changes

Let `y` be the old nonlinear observation. The translation view gives `u = y + b`.
The remix view gives `u = Q y + b`, where `Q` is a dense orthogonal matrix formed from two
Householder reflections. A fixed random seed generates both before fitting; the resulting
numeric offset and matrix are registered. Neither is selected using task quality, action
rules, generator product connections or the coupling layout. Orthogonality preserves
Euclidean distances and avoids a new ill-conditioning confound in the observation map.

The learner receives transformed initial vectors, action indices and transformed observed
consequences. It receives no paired old/new views, matrix, offset, known inverse, canonical
state or parent-encoder target. The experimenter chooses the version at a declared regime
boundary; autonomous routing between representations is not tested. There is no sensor
inverse or preprocessing bridge hidden in the deployed prediction path.

Translation is a controlled capacity check: for any existing four-coupling encoder,
precomposing a translation can be expressed by changing the first coupling's input bias
and the first two couplings' output biases. An independent synthetic test verifies this
algebra and inverse decoding. This construction never initializes a candidate, supplies
targets or uses the acquired private weights. The dense remix probes a less constrained
change; failure there cannot alone distinguish optimization from representational limits
under fixed operations.

These views remain coordinate changes in the same fully observed finite world. Underlying
development trajectories were already used by EXP-0009, while their new observations are
held out from adaptation training. This tests a new input representation of acquired
behavior, not unseen world dynamics or fresh final evidence. Final trajectories remain
unrendered. Structural preflight may inspect non-final observations for float32 input,
injectivity and partition audits, but model development-quality evaluation stays gated.

## Bounded execution and selection

First replay each of the three old parents on its old-regime development and continuation
cases and record zero-shot one-step acquisition on both new views. Every arm retains the
old snapshot unchanged. This preserves competence by keeping a version, not by demonstrating
an absence of interference in a shared changing encoder. Each new run embeds the exact old
snapshot needed for recovery, and frozen arms check operation identity after every update.

Run all 24 one-step fits at the single previously effective rate, 0.01: four arms, two views,
three seeds and 4,096 updates. Views have independent gates; failure on translation does
not block remix. Select the earliest saved checkpoint passing every prediction,
reconstruction and action floor. If none passes, retain the minimum-loss failure. The full
duration is always executed and charged.

Only an arm/view whose three seeds acquire and fully replay may run its three 2,048-update
familiar short-rollout fits. Each starts from its own selected one-step checkpoint with
fresh Adam. Only after all three mixed fits acquire and replay may it evaluate new-view
development compositions and paired continuations from its own states. Retain the existing
state erasure, action reversal, provided-current-observation diagnostic and saved-state checks.
The selected snapshot is the first acquired checkpoint, so its later competence result
can be connected to recorded acquisition-point work without choosing a cheaper checkpoint
after seeing development scores.

Require every seed to pass the registered total, family and continuation floors. Report
results by view. Translation success alone does not establish competence across both views.
A failed from-scratch comparator cannot support a practical advantage claim. The protocol
defines a descriptive acquisition-point cost criterion only when both compared systems are
competent. Keep this separate from actual full-duration consumption and uncontrolled local
elapsed times.

## Cost, provenance and scope

The maximum is 48 fits, 24 conditional evaluations, three parent baselines, two synthetic
preflights, one injected post-fit failure and 83 replays, including eight restored-source
samples: 161 attempts. Registration caps 150,000 gradient updates, 3.4 million affine-fit
examples, 27,000 linear systems, 256 MiB of run artifacts and one hour of recorded run time.
Each run remains within 120 seconds, 16 MiB and 2 GiB RSS. Serialize local work.

Record actual fitting, baseline and verification costs and work at every acquisition
measurement. Account for benchmark observation transforms separately from learned encode/
decode work. Include the complete upstream EXP-0009 acquisition campaign once as shared
cost; also identify each retained parent lineage. Reusing values is not free acquisition
or free storage. New runs contain both an old snapshot and their new snapshots; report
physical bytes without assuming parameter deduplication.

Replay all checkpoint measurements, selection decisions, frozen-operation checks, affine
refits and conditional predictions. Verify private archival and restored-source inference
under the owner-selected same-disk retention arrangement before closing. No unique data
is deleted. No new runtime, physical provider, objective, model width or final-data sweep
is part of this study. After its bounded decision and delivery, any next research question
requires another explicit queue decision.
