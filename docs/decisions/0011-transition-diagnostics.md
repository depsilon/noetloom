# Decision 0011 — Affine explanation and complete-rollout diagnostics

Date: 2026-09-30. Work item: N-011, diagnostic portion only. Status: retain the
EXP-0006 component result with a stronger simple reference; proceed to the learned-state study.

The [separate registration](../../experiments/EXP-0007/diagnostics.json) and
[reader repair](../../experiments/EXP-0007/diagnostics-repair.json) do not change N-008,
N-010 or EXP-0006's frozen verdict. The review's external archive was not inspected.
This implementation fitted its own ordinary affine learner from the permitted observed
examples and evaluated the retained neural checkpoints. [Compact evidence](../evidence/N-011-diagnostics-2026-09-30.json)
contains every seed, family, prefix audit, attempt and recovery identity.

## Measured result

| Predictor | Development trajectories correct at every prefix | Exact prefixes |
| --- | ---: | ---: |
| Affine identification from 640 one-step observations | 608/608 | 1,920/1,920 |
| Retained one-step neural snapshots, each of three seeds | 608/608 | 1,920/1,920 |
| Retained mixed-stage neural snapshots, each of three seeds | 608/608 | 1,920/1,920 |

The affine predictor evolves continuous outputs without intermediate rounding or true-state
injection. Its fitter accepts only observed input/action/target triples, never permutations,
flip masks or the simulator. Maximum continuous bipolar-coordinate error was `0.0` in this
implementation; the external review used different numerical arithmetic. This is an exact
finite-domain identification result, not a speed comparison or a confirmed architectural win.

The candidate's perfect endpoints conceal no intermediate errors on these development cases.
The retained one-step snapshots are already sufficient at this metric's ceiling, so mixed
training shows no exactness gain here. This does not establish equivalence on untested
robustness, probability calibration or other environments.

All 24 selected-fit training/validation prediction sets and three retained development sets
were audited. The six mixed GRU validation sets have respectively 0, 3, 3, 1, 3 and 2
trajectories with an incorrect prefix followed by a correct endpoint (three seeds at each
of the two original learning rates). Their first-step predictions are correct; first errors
occur at step two or three. This describes saved behavior without diagnosing why it occurred.

## Integrity, costs and limits

The first attempt completed its affine solve but failed before comparison scoring because
the new reader omitted the original transfer file's `rows` wrapper. That failed attempt and
its completed fit remain intact. A committed implementation repair exchanged one unused replay
allowance for a repair run within the original four-attempt, 64 MiB and 480-second ceilings.
No fitting or scoring definition changed. Missing usage in the failed attempt is charged at
its registered ceilings, not silently treated as zero work.

The repaired run, full fresh-process replay, and replay using restored inputs and restored
committed source all pass. The three successful attempts each audit 21,344 trajectories,
recompute six checkpoints and refit the affine reference. Every mixed checkpoint reproduces
its historical loss, predictions, logits and endpoint metrics exactly; independent scalar
equations also check all six checkpoints. Reserved final trajectories remain unrendered.

The owner-selected private backup preserves all original attempts and committed source, with
the recovery attempt and adapter alongside it. All 299 archived entries restored correctly;
the recovery replay is separately inventoried. This is a same-disk duplicate using the local
PyTorch environment, not protection against disk loss or a portable environment attestation.
All 165 Python tests, contract checks and 12,096-prediction harness replay pass; source commit
`5901b29cec03693b116bdffd050085e9ac69ee77` passed hosted Linux and macOS checks.

## Consequence for N-011

Do not optimize this benchmark further or extend the failed GRU sweep. Keep affine
identification as a regression reference. The next study must earn representation learning
under a structured invertible nonlinear observation mapping, with the same latent transition
family and a matched consistency contrast. Correct shared-suffix behavior after different
histories reaching the same state is the functional reuse test. Underlying state interactions
belong to a later separate experiment; storage integration remains outside scope.
