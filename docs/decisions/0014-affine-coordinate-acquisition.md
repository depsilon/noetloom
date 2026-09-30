# Decision 0014 — Affine refitting acquires nonlinear reusable transitions

Date: 2026-09-30. Work item: N-013. Status: retain this bounded acquisition recipe and
its learned operation snapshots; next test representation change with retained operations.

The [registered optimization comparison](../../experiments/EXP-0009/protocol.json) ran from
committed source `a01563bbb48c8f6fe8d35c37f892774560213cd0`. Its
[evidence record](../evidence/N-013-affine-coordinates-2026-09-30.json) retains all 15 fits,
99 acquisition measurements, three development evaluations, every affine refit and every
attempt. EXP-0008's failures and isolated oracle remain unchanged.

Fitting affine operations from the current learned coordinates passes all acquisition and
development gates in the three registered seeds at rate 0.01. Joint gradient fitting does
not pass acquisition across all seeds. This is a useful component result in one finite,
fully observed world, not a confirmed general architecture or practical cost advantage.

## What changed

Both arms retain the same 1,780-parameter reversible model, nonlinear observation map,
observed examples, prediction objective, sampling and gradient-update ceiling. Joint Adam
updates every parameter. The refit arm uses Adam for the 1,340 coupling parameters and
recomputes the 440 affine coefficients from current encodings of permitted observed pairs.
Each action solve has 128 rows and 11 input-plus-bias columns. The solver is detached;
prediction gradients subsequently pass through the fixed maps into the learned mapping.

Refitting occurs at initialization and every 32 updates. It receives no new underlying
observations, canonical states, world rules, known inverse, oracle weights or old learned
snapshots. It does repeatedly process the full training pool, so equal gradient-update
ceilings are not equal total computation. The [design](../../experiments/EXP-0009/design.md)
records this distinction and the limited relationship to the established LKIS method.

## Acquisition and decoded composition

One-step validation correctness below requires every coordinate to be within 0.25 on each
of 128 observations. Passing additionally requires the registered training, reconstruction
and action floors. Both rates and all seeds completed before condition selection.

| Optimizer / rate | Seed 13003 | Seed 13009 | Seed 13027 | Seeds passing all gates |
| --- | ---: | ---: | ---: | ---: |
| Joint / 0.003 | 0% | 83.59% | 99.22% | 1/3 |
| Joint / 0.01 | 74.22% | 100% | 100% | 2/3 |
| Refit / 0.003 | 80.47% | 100% | 99.22% | 2/3 |
| Refit / 0.01 | 100% | 100% | 100% | 3/3 |

The refit arm selects rate 0.01. All three selected one-step snapshots occur at step 4,096
and have 100% training and validation correctness. Their three familiar short-rollout fits
also pass, with selected steps 512, 1,024 and zero respectively. Every mixed fit still
completes and charges its full 2,048 updates. Step-zero selection in the third seed shows
that its existing one-step parameters already suffice for this acquisition measurement;
it is not evidence that mixed optimization improved every model.

All three selected mixed snapshots then predict:

- 608/608 development trajectories, including every one of their 1,920 intermediate
  prefixes and all registered families through length six;
- 64/64 paired continuations after different histories reach the same underlying state,
  using each model's own retained state;
- identical continuations after saving and reopening eight sampled intermediate states.

Maximum development coordinate errors are 0.16080, 0.10088 and 0.11953, below tolerance
0.25. Every recorded reconstruction measurement across both arms passes; the largest
reconstruction error is 1.19e-6. These observations establish decoded performance rather
than relying on a small latent least-squares residual.

Erasing the initial observation reduces development correctness to 0/608. Erasing state
after history reduces successful paired continuations to 0/64, even though the resulting
states agree with each other. Reversing action order yields only 166/608 correct original
trajectories; single-step and order-insensitive cases explain some residual success.
Resetting from the provided true current observation remains 64/64 and is explicitly an
assisted diagnostic. It is not the candidate's normal inference path.

The joint arm has no admitted mixed or development evaluation. Its acquisition failure
cannot establish a practical advantage over a competent comparator. The improvement in
passing-seed counts is descriptive evidence for this optimization change under the fixed
development protocol. There is no significance claim, new-world confirmation or final-data
access. The direct predictor's separate EXP-0008 failure is not a new comparison here.

## Integrity, resources and recovery

All 15 fits and three evaluations have complete ordinary replays. Each fit replay
recomputes every acquisition checkpoint and selection; refit replays also reconstruct
every scheduled solve from its saved encoder and the permitted training observations.
The nine refit fits contain 969 refits and 3,876 action systems. Every system has rank 11;
the largest condition number is 18.71 and normalized normal-equation residual is 2.04e-15.
There are no solver fallbacks or replacement seeds.

Eight additional representative results pass replay from restored artifact bytes and the
archived executable source, covering both optimizers, failed acquisition, both fitting
stages and development evaluation. The full total is 46 attempts: 15 fits, three evaluations,
26 replays, one synthetic preflight and one deliberately injected verification failure.
That injection retains completed eight-update fitting separately from failed verification.

Including preflight, injection and all replays, recorded work totals 55,336 gradient updates,
631,460 example presentations, 749,436 forward prefixes, 3,899,132 auxiliary observation
presentations, 1,191,080 affine-fit examples and 9,312 linear systems. Recorded process time
is 310.52 seconds, maximum worker RSS is 328,204,288 bytes, and charged run storage is
72,114,176 bytes (66,999,186 logical file bytes). Archive I/O, unit tests and offline report
construction are outside those run totals. The injected failure lacks a returned supervisor
sample summary but retains worker high-water RSS and elapsed time.

The six one-step fits per arm use the same 24,576 gradient updates. Joint fitting records
59.07 seconds and 473,856 auxiliary observation presentations; refitting records 55.84
seconds, 1,266,432 auxiliary presentations and 396,288 affine-fit examples. This uncontrolled
local elapsed-time difference does not establish a speedup. Dense model arithmetic, solver
matrix dimensions, solver time, backward calls and parameter updates are recorded separately;
the counters are not complete SVD or backward FLOP estimates.

The private archive contains all 38 ordinary attempts and committed source, with all 1,599
entries restored and hash-verified. Its SHA-256 is
`8017bfca3f958f4a83fa810d28cc9675b4e8a3502e439ad819bd0b0707b9b797`.
All eight recovery-run outputs have separately verified copies. Recovery uses the existing
numerical environment. The owner-selected destination is on the same disk, and no artifact
is retired. These parameter snapshots support inference replay, not exact Adam continuation.

The default Python suite reports 232 passed and 13 optional tensor tests skipped. All nine
new optional tensor tests pass in the admitted environment (the two focused suites contain
12 tests in total). Repository contracts, host admission and the refreshed EXP-0001 replay
of 12,096 predictions pass. The frozen source passes Linux/macOS Python and Rust checks in
[run 36787318351](https://github.com/depsilon/noetloom/actions/runs/36787318351).
The final evidence commit also requires successful hosted checks.

## Next decision

Select N-014 to test a representation bridge while retaining these acquired operations.
Use separately registered changes to how the same world is observed, freeze the retained
operation parameters, and compare new-representation acquisition with a credible from-scratch
control. Separate reuse of operation parameters from reuse of mapping initialization.
Audit exactly what old/new observations and paired supervision each arm receives. No known
inverse or simulator-state target may enter the learner.

Register adaptation limits, all-seed acquisition and composition gates before fitting.
Charge inherited acquisition, retained parameter storage, conversion and adaptation work;
report marginal adaptation separately from total lifecycle cost. Verify old competence and
the identity of retained operations, while distinguishing immutable old-version retention
from learning without interference in shared changing parameters.

This next bounded study concerns an observation change with fixed dynamics. Broader task
changes, interacting dynamics, partial observation, compression, bounded memory and a
physical provider role remain separate research questions. Preserve the existing runtime
and model size; do not turn this result into a broad architecture reset.
