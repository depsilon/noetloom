# Decision 0013 — Nonlinear coordinates are learnable, but acquisition remains unreliable

Date: 2026-09-30. Work item: N-012. Status: retain the capacity witness and individual
learned successes; close this calibration and separately test affine identification.

The [registered comparison](../../experiments/EXP-0008/protocol.json) ran from committed
source `b9841fc5888048f7b0ba5173c08b4233966e04ff`. Its
[evidence record](../evidence/N-012-coordinates-2026-09-30.json) contains all 36 fits,
216 saved acquisition checkpoints, every gate, local perturbation, replay, cost and recovery
identity. EXP-0007 and its failed configurations remain unchanged.

The result resolves two uncertainties. A constructed solution exists inside the original
family, and ordinary learning can discover useful nonlinear coordinates in individual seeds.
Preserving reconstruction does not, by itself, make that learning reliable across seeds.

## Capacity and the controlled comparison

We independently constructed the analytic witness described in the review. Six active tanh
units in each residual mapping express the three product corrections on the finite bipolar
domain; the remaining units are unused. The original 1,804-parameter family predicts all
512 permitted one-step cases and all 64 training-only six-step paths correctly, including
every intermediate prefix. Maximum float32 prediction error is 4.77e-7 against tolerance 0.25.
An independent scalar implementation agrees. These weights use known world rules and are
an isolated oracle diagnostic, never candidate initialization, training data or evaluation
assistance. The review's downloadable diagnostic archive was unavailable; this is our own
construction and reproduction, not verification of that archive.

The learned comparison retains the four affine action maps. Independent residual encoder
and decoder networks have 1,804 parameters. Four generic additive coupling layers with an
explicit learned inverse have 1,780. Their even/odd layout is independent of the generator's
product connections. Both start with identity mappings and identical seeded transition
parameters. The [design](../../experiments/EXP-0008/design.md) records the established NICE
mechanism, supplied structure, objective and compute differences.

The unchanged 5,416-parameter direct nonlinear predictor receives its own acquisition trial
on nonlinear observations. All three systems use the same observed examples. No learner
receives canonical state, known inverse, oracle weights or held-out training targets.
Consistency remains off. The earlier aligned continuation baseline was already 64/64;
its required +0.10 improvement was unavailable at that ceiling. That result demonstrates
no benefit there, not that consistency cannot help elsewhere.

## Acquisition results

Every arm, rate and seed starts independent tiny and larger one-step fits. Tiny fitting uses
32 pairs and 2,048 updates; one-step fitting uses 512 pairs and 4,096 updates. Tiny failure
does not block the larger cohort. Both data coverage and duration differ between cohorts,
so their difference is not an isolated causal estimate of coverage.

The one-step table reports selected validation correctness on 128 pairs. A pair is correct
only when every observed coordinate is within 0.25. Passing also requires the registered
training, reconstruction and action-slice floors; selection cannot rescue a failed seed.

| System / rate | Seed 12003 | Seed 12009 | Seed 12027 | Seeds passing all gates |
| --- | ---: | ---: | ---: | ---: |
| Independent mappings / 0.003 | 99.22% | 33.59% | 14.84% | 1/3 |
| Independent mappings / 0.01 | 100% | 14.06% | 100% | 2/3 |
| Reversible mappings / 0.003 | 89.06% | 100% | 60.94% | 1/3 |
| Reversible mappings / 0.01 | 100% | 82.03% | 100% | 2/3 |
| Direct predictor / 0.003 | 0.78% | 0% | 0.78% | 0/3 |
| Direct predictor / 0.01 | 0.78% | 0.78% | 0% | 0/3 |

Reversible reconstruction is correct at every saved training and validation measurement;
its largest coordinate error is 1.08e-6. Its mean one-step validation accuracy is higher at
both rates: 83.33% versus 49.22%, and 94.01% versus 71.35%. However, passing-seed counts are
identical. At the lower rate one paired seed becomes worse. These are descriptive development
results from three seeds in one world, not a confirmed mechanism advantage or a reliable
acquisition configuration.

Tiny acquisition passes 1/3 seeds for each mapping family at rate 0.003, and 0/3 at 0.01.
All three lower-rate independent fits predict every tiny pair correctly, but two fail
reconstruction, at 73.44% and 87.5% selected reconstruction accuracy. Reversibility removes
that failure mode while leaving prediction failures possible.

The direct predictor passes tiny acquisition in all three lower-rate seeds, and none at
the higher rate. On the larger cohort, its selected training accuracy is 44.34–46.68% at
0.003 and 12.11–19.92% at 0.01. Its failed validation is therefore accompanied by poor
training fit. This bounded baseline does not establish the limits of direct predictors.

No arm passes one-step acquisition in all three seeds at a common rate. Consequently, no
mixed-rollout fit is admitted. No development-composition or final trajectory is rendered.
The oracle's six-step success must not be presented as learned multi-step performance.

## Local prediction updates and reconstruction

The registered probes copy each checkpoint, apply one prediction-only clipped SGD step to
a selected parameter group, measure its effects, then restore the original parameters.
They do not change the actual Adam trajectory.

At initialization, encoder-only and decoder-only steps in the independent family each
reduce prediction MSE while increasing reconstruction MSE. The increases are small:
approximately 1.3e-6–1.9e-5 for the encoder and 1.2e-6–1.5e-5 for the decoder. Reconstruction
still passes tolerance. Later encoder changes can improve or worsen reconstruction;
the measurements do not establish a universal gradient conflict or a collapse mechanism.
Reversible reconstruction remains within numerical roundoff under the probes.

This supports making preservation of information an explicit experimental constraint in
this equal-width, fully observed setting. It does not require future Noetloom representations
to be invertible, especially when compression, noise or partial observation matter.

## Integrity, cost and delivery

All 36 fits and the oracle have complete ordinary replays. Eight representative results
also replay from a restored private copy and archived source, including all three systems,
both cohorts and acquisition failures. The total is 84 attempts: 36 fits, 45 replays, one
oracle, one preflight and one deliberately injected verification failure. The injection
retains completed fitting and failed verification as distinct outcomes. All recorded
artifact bytes, fit identities, checkpoint steps, gates and selection decisions are checked.

The campaign charges 111,206 updates, including 558 local probe updates; 1,121,096 example
presentations; 1,123,976 predicted prefixes; and 1,624,168 auxiliary observation presentations.
Recorded process time totals 307.55 seconds. Maximum worker RSS is 318,308,352 bytes;
run artifacts occupy 28,635,136 charged bytes, with 24,072,344 logical file bytes. These
are within the registered limits. Archive I/O and offline report construction are outside
those run totals. The injected failure has no returned supervisor sample summary, but
retains worker high-water RSS and elapsed time.

Across the 12 primary fits per system, recorded elapsed time totals 47.77 seconds for
independent mappings, 69.03 for reversible mappings and 42.96 for the direct predictor.
Conversions, reconstruction checks and different probe-group counts are included. Forward
arithmetic, backward calls and parameter updates remain separate counters; these are not
complete FLOP estimates or evidence of a practical speed advantage.

The private archive restored and hash-verified all 1,199 entries. Its eight recovery outputs
and analysis scripts have separately verified copies. The archive SHA-256 is
`16606594b48edf3be225c09e60455aeb33169b309ec692802017f11bda68bcc0`.
The owner-selected private destination is on the same disk and recovery uses the existing
numerical environment. No checkpoint is retired.

The default Python suite reports 223 passed and four optional tensor tests skipped; those
four also pass in the admitted tensor environment. Repository contracts, host admission
and the refreshed EXP-0001 replay of 12,096 predictions pass. The frozen source passed
Linux/macOS Python and Rust checks in
[run 36781481612](https://github.com/depsilon/noetloom/actions/runs/36781481612).
The final evidence commit must also complete hosted checks.

## Next decision

Select N-013 as a separate optimization comparison on the retained reversible family:
joint Adam versus fitting affine transitions from current encoded training observations
while learning the representation. Fix the mapping architecture so that the next comparison
isolates this optimization change. Reversibility is retained for its verified reconstruction
property and promising development scores, not declared the winning foundation.

Before fitting, register the solver, rank/conditioning checks or regularization, refit
schedule, gradient treatment, fresh seeds, matched information access and numeric work limits.
Use sufficiently informative permitted training support; do not fit eleven affine coefficients
from eight examples without declared handling. Retain decoded one-step and free-running
multi-step acceptance: a small latent least-squares residual alone is insufficient. Charge
every encode, solve, refit and replay. Keep width, consistency and the underlying world fixed.

The longer-term question remains whether an observation bridge can preserve already learned
operations when representation changes, compared with retraining and with adaptation cost
included. That requires its own falsifiable experiment after reliable acquisition; neither
this pilot nor the next solver comparison establishes continual learning or a provider role.
