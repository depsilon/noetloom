# EXP-0009 — Fit affine operations inside learned coordinates

N-013 is a separately registered optimization comparison following
[Decision 0013](../../docs/decisions/0013-coordinate-acquisition.md). EXP-0008 showed
individual nonlinear acquisition and preserved reconstruction with reversible mappings,
but neither mapping family acquired across all three seeds at a common rate. This trial
keeps the reversible model fixed and changes how its affine action maps are fitted.

## Mechanism and boundaries

Both arms use the same 1,780-parameter model, world, observation map, partitions, batch
sampling, prediction objective and two rates. Seeds 13003, 13009 and 13027 are fresh.
The joint arm updates all parameters with Adam. The refit arm updates the 1,340 coupling
parameters with Adam, while its 440 affine coefficients are fitted from current encodings
of observed training pairs. No oracle, canonical labels, known inverse or old weights enter
either arm. This is a limited component comparison, not Noetloom's proposed foundation.

For each action, the refit arm solves a float64 least-squares system with 128 rows and
11 input-plus-bias columns. Its targets are the same learned encoder applied to the
observed training consequences. The fit is refreshed at step zero and every 32 gradient
updates, including the final step and before measurement. All four maps are published
together only after their checks pass. The encoder is not changed by a refit.

The solver uses CPU `torch.linalg.lstsq` with explicit `driver="gelsd"` and
`rcond=1e-10`. Require rank 11, finite coefficients, condition number at most 1e8,
and normalized normal-equation residual at most 1e-10. There is no regularization or
fallback. This follows the [PyTorch 2.14 API](https://docs.pytorch.org/docs/2.14/generated/torch.linalg.lstsq.html)
for an explicit rank-revealing solve; numeric settings are this experiment's choices.
The maps are cast back to float32, and both float64 and deployed-coefficient residuals
are retained. Rejected rank or conditioning closes that attempt without a replacement seed.

The solve and encoded targets are detached. Subsequent prediction gradients pass through
the fixed maps into the encoder and inverse decoder until the next refit. We keep the
decoded prediction objective, including its numerically near-zero reconstruction term.
There is no new latent loss or implicit differentiation through the solve.

[LKIS](https://proceedings.neurips.cc/paper_files/paper/2017/file/3a835d3215755c435ef4fe9965a3f2a0-Paper.pdf)
sections 3.1–3.4 motivate fitting a linear subproblem in learned observables, state a rank
requirement and constrain trivial representations through reconstruction. Our alternating
detached solves, controlled actions and decoded objective are a distinct experiment,
not a reproduction of its residual-minimization method or its empirical results.

## Registered stages and interpretation

The [protocol](protocol.json) fixes twelve one-step fits: two optimizer arms, two rates,
three seeds, 4,096 gradient updates each. Tiny fitting is already characterized by EXP-0008
and is not repeated or used as a prerequisite. Both rates complete before selecting the
first rate where every seed passes all training, validation, reconstruction and action
floors. An earlier passing checkpoint may be selected, but every update remains charged.

Each qualifying arm then runs three 2,048-update familiar short-rollout fits, each from
its own selected one-step snapshot with a fresh optimizer. In the refit arm, maps continue
to use the same one-step training pool; mixed prediction supervision uses its permitted
observed prefixes. This pool is available to the joint arm from its one-step stage.
The refit arm repeatedly processes it, and that additional work is charged explicitly.

Only if all three mixed fits pass and fully replay may an arm render development
compositions and common-state continuation pairs. This tests decoded predictions from
the model's own state, with action reversal, erased initial information and state
interventions. It is separate from fitting the latent residual. Success requires every
seed to meet the total, family and continuation floors. If only one arm acquires, its
development result is a scoped competence result; the failed arm cannot establish
practical superiority. Final trajectories remain unrendered by this trial.

## Evidence and work accounting

Save every acquisition checkpoint and every scheduled refit's full post-fit parameters
and diagnostics. Replay all solves using those saved encoders, regenerate the permitted
training observations, compare maps and reports, recompute every acquisition measurement
and selection, and replay all conditional development predictions and interventions.
A constructed full-rank affine fixture with nonzero bias checks orientation independently;
rank-deficient and malformed inputs must be rejected. Verify that coupling tensors do not
change during a solve and transition tensors do not change during refit-arm Adam updates.

Compare results and total work at common rates and seeds. Matching gradient-update ceilings
is not matching total compute: refitting processes extra training examples. Charge both
encoder passes, affine-fit examples, matrix dimensions and linear-system calls, fitted
coefficient assignments, backward calls, parameter updates and elapsed time. Model dense
arithmetic does not include complete SVD or backward FLOPs; do not infer a speed advantage.

At most 18 fits, six conditional evaluations, two synthetic preflights, one injected
post-fit verification failure and 34 replays fit within 61 attempts, 65,000 gradient
updates, 1.6 million affine-fit examples, 256 MiB of run outputs and one hour of recorded
process time. Per-run limits remain 120 seconds, 16 MiB and 2 GiB RSS. Serialize all runs.
The prior pilot has a verified private duplicate and restored-source replay. Use the same
owner-authorized destination pattern, verify this trial's archive and representative
restored-source replays, and retain the stated same-disk limitation. Delete no unique data.

Close with a retain/revise/reject decision and exact delivery checks. A later bridge that
changes representation while retaining learned operations, or a confirmatory comparison,
requires its own evidence-based queue decision and numeric registration.
