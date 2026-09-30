# Decision 0012 — State reuse works when aligned; nonlinear acquisition remains unresolved

Date: 2026-09-30. Work item: N-011. Status: retain the aligned component evidence;
reject these nonlinear acquisition configurations and revise calibration. The broader
learned-representation hypothesis remains unresolved.

The [registered pilot](../../experiments/EXP-0007/protocol.json) ran from committed source
`1471e8d9bd14742ee35825b8bc4307927dabc934`. Its
[evidence record](../evidence/N-011-state-representation-2026-09-30.json) contains every
arm, rate, seed, acquisition stage, transfer family, failed gate, attempt, cost and recovery
identity. The [preceding diagnostic](0011-transition-diagnostics.md) remains separate from
the new world. EXP-0006, N-008 and N-010 are unchanged.

## What changed in the test

The fresh ten-dimensional world supplies observed vectors and ordered actions. Three
quadratic shears create a structured invertible nonlinear observation mapping; neither
learners nor scorers receive its inverse or canonical-state labels. Training and auxiliary
reconstruction targets never expose held-out states. The audit found 484 distinct observed
training states and zero held-out-state overlap. Development can revisit training states;
it does not claim every intermediate observation is unseen.

Two learned encoder/decoder systems share the same action-specific affine transition family
and 1,804-parameter architecture. Their only objective difference is a declared consistency
term with a stopped target-encoder gradient. Both receive prefix observations and reconstruction
supervision. The 5,416-parameter direct control instead updates its own predicted observations
with action-specific nonlinear networks. The 440-parameter ordinary affine reference is fit
only from observed one-step triples. No GRU sweep was extended.

Complete-rollout correctness requires every observed coordinate within 0.25 of its target
at every step. The continuation test uses 64 distinct actual states, each reached by two
different familiar histories, followed by the same unfamiliar suffix. Predictions continue
from each model's own state. Correctness, wrong agreement, and latent-state distance are
separate measurements.

## Results

| Observation / system | Acquisition | Development correct at every prefix | Both-history continuation correct |
| --- | --- | ---: | ---: |
| Aligned affine reference | Exact one-step training and validation | 608/608 | 64/64 |
| Aligned learned mappings | All three seeds at rate 0.01 | 608/608 in every seed | 64/64 in every seed |
| Aligned mappings + consistency | All three seeds at rate 0.01 | 608/608 in every seed | 63/64, 64/64, 64/64 |
| Aligned direct nonlinear predictor | Failed one-step validation at both rates | Not admitted | Not admitted |
| Nonlinear affine reference | 0/512 training and 0/128 validation complete observations | 0/608 | 0/64 |
| Nonlinear learned mappings, either objective | All 12 fits failed tiny-set acquisition | Not admitted | Not admitted |

The aligned latent arms also failed the tiny gate at rate 0.003. The registered higher rate
passed all stages for both, with 100% selected training and validation accuracy. Every update,
including work after an earlier qualifying checkpoint, remains charged. Mixed-stage selection
sometimes chose step zero; this is not evidence that additional mixed training was necessary.

The direct control fitted the tiny set in every seed. At rate 0.003 it reached 100% one-step
training accuracy but selected validation accuracies of 92.2%, 85.9% and 87.5%, below the 95%
gate. At 0.01 its selected training and validation accuracy were lower. Its six potential
nonlinear fits were therefore not admitted. This failed control cannot establish practical
superiority; the competent aligned affine reference already solves that domain exactly.

On nonlinear observations, the selected tiny-set prediction accuracies were:

| Arm / rate | Seed 11003 | Seed 11009 | Seed 11027 |
| --- | ---: | ---: | ---: |
| Learned mappings / 0.003 | 0% | 0% | 0% |
| Learned mappings / 0.01 | 59.4% | 65.6% | 78.1% |
| Consistency / 0.003 | 3.1% | 6.3% | 0% |
| Consistency / 0.01 | 46.9% | 65.6% | 62.5% |

These are acquisition failures after the fixed 256 updates, not nonlinear transfer scores.
Every nonlinear fit also failed the reconstruction gate; even at the higher rate, selected
complete-observation reconstruction accuracy was only 25.0–46.9% without consistency and
28.1–32.8% with it. Lower losses or finite gradients cannot substitute for retained task
information. These measurements do not identify representation collapse, inadequate capacity,
loss weighting or insufficient duration as the cause. The fitting regime needs calibration
before an architecture-level interpretation.

## What the continuation controls show

All six aligned models decode both current observations correctly in all 64 pairs. Their
latent vectors differ across histories, yet the learned-mapping arm continues correctly in
every pair. This supports functional state reuse without requiring identical coordinates.
Erasing the initial state or zeroing state after the histories reduces complete correctness
to zero. Reversing actions affects every composition family, with oracle sensitivity recorded;
the unchanged one-step cases are not evidence about order.

Consistency seed 11003 makes one continuation error at suffix step four despite close
agreement between its two predictions. The scorer counts that as wrong agreement, not success.
An explicitly labeled reset to the provided true current observation removes this error.
That is a scoped intervention result, not proof that hidden-state drift caused prior GRU
failures or that all latent-state differences are harmful.

The mean paired consistency change is −0.00521 in unconditional continuation accuracy, with
seed differences −0.015625, 0 and 0. It fails the registered +0.10 effect threshold and the
no-negative-seed requirement. There is no measured consistency advantage here. Three seeds
in one finite world do not support query-level confidence intervals or a general claim.

## Integrity, costs and closure

There were 30 neural fits, two affine fits, six transfer evaluations, one preflight, one
deliberately failed post-fit verification test, 38 ordinary complete replays and eight
restored-source replays: 86 attempts. Every ordinary result reproduces its full recorded
predictions or every acquisition measurement and selected checkpoint. A separate bookkeeping
audit checks stage order, measurement steps, selected gates, aggregate qualification flags,
source identities and all artifact bytes. The injection retains completed fitting and failed
verification as distinct outcomes; no failed acquisition is promoted to success.

The campaign used 44,600 gradient updates, 579,304 trajectory presentations, 827,092 predicted
prefixes, 1,272,736 auxiliary observation presentations, and 3,072 affine-fit examples including
refits. Worker/supervisor elapsed time totals 323.75 seconds. Maximum recorded RSS is
322,830,336 bytes; run artifacts have a conservatively charged on-disk footprint of 79,663,104
bytes (75,235,076 logical file bytes). All are within registration.
Dense forward arithmetic, backward-graph calls and parameter-update elements are reported
separately; no complete training-FLOP or hardware-efficiency claim is made. The injected
failure lacks a returned supervisor sampling summary, but retains worker high-water RSS and
elapsed time. Archive I/O, offline analysis and prior campaigns have separate scope.

Private aligned and nonlinear archives restored all 1,123 and 445 entries, respectively.
Eight representative fits/evaluations then replayed from restored inputs and committed source,
including all three learned arm types, both observation views and the observed continuation
error. Recovery outputs and the adapter are separately copied and byte-verified. The selected
private destination remains on the same disk and uses the existing numerical environment;
it is not an independent disk-failure domain. No checkpoint is retired.

All 205 Python tests, repository contracts, host admission and the 12,096-prediction harness
replay pass. The frozen source passed hosted Linux/macOS Python and Rust checks in
[run 36774378453](https://github.com/depsilon/noetloom/actions/runs/36774378453).

No nonlinear neural transfer or final evaluation was admitted. The aligned ceiling alone
does not warrant confirming the intended nonlinear-representation claim. All reserved final
trajectories remain unrendered. Close N-011 at its registered boundary.

## Next decision

Select N-012: calibrate joint representation acquisition before another composition claim.
Use the retained tiny-set prediction/reconstruction curves to register one bounded diagnostic
that can distinguish fitting difficulty from a failure of the intended representation family.
Review whether the initial tiny curriculum and coupled objectives are informative, and include
an explicit representability check and an acquired relevant comparison. Keep diagnostic oracle
structure clearly separated from candidate runtime and training information. Freeze any changed
duration, loss, curriculum or initialization before fitting; do not append trials to EXP-0007.

The next item does not authorize new underlying state interactions, a pretrained runtime
solver, provider changes or an unbounded sweep. Acquisition failure leaves the representation
question open; it does not justify replacing the research goal with the successful affine toy.
