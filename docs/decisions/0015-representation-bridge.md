# Decision 0015 — Retained operations do not reliably bridge the observation change

Date: 2026-09-30. Work item: N-014. Status: close the registered bridge study with a
negative reliable-reuse result; retain the acquired reference and all failed attempts.

The [registered study](../../experiments/EXP-0010/protocol.json) ran from frozen source
`2bd146ae04cc46fc10850d32caee1e40a071d3b4`. Its
[evidence record](../evidence/N-014-representation-bridge-2026-09-30.json) contains all
100 attempts, artifact identities, acquisition curves, conditional evaluations, cost
attribution and recovery evidence. EXP-0009 and its successful acquired parents are unchanged.

Keeping the acquired operations fixed does not pass the three-seed competence requirement
under either new observation view. With translated observations, retaining the old mapping
initialization permits early acquisition in every seed, but two fail later competence gates.
Both controls that refit operations pass all three translation seeds. No arm acquires all
three seeds under the dense remix, so its composition evaluations are not admitted.
This study establishes neither reliable frozen-operation reuse nor its claimed cost benefit.

## Comparison and information access

All four arms use the same 1,780-parameter reversible model, world dynamics, observed
consequences, batches, rate 0.01 and update ceilings. They cross retaining versus resetting
the learned mapping with freezing versus refitting the 440 operation coefficients. Adam
updates only the 1,340 mapping parameters in every arm. Refit arms also solve for operations
from current encodings of the permitted training observations, at initialization and every
32 updates. Those full-pool encodings and solves are additional charged work.

The new views are a translation, `u = y + b`, and a dense orthogonal remix, `u = Qy + b`,
of the old nonlinear observation. The learner receives the new initial observation, actions
and new observed consequences. It receives no transform matrix, offset, inverse, canonical
state, paired old/new targets or old-encoder targets. The experimenter supplies the regime
boundary; autonomous representation routing is not tested.

An independent synthetic test proves that the mapping family can express the translation
while preserving arbitrary fixed operations. Its constructed weights never initialize a
candidate. No corresponding fixed-operation capacity claim is made for the dense remix.
The input audit finds distinct float32 observations for all 811 audited states, no conflicting
input signatures and no training/validation/development input-prefix overlap. Old and new
training signatures also have zero overlap. The underlying development trajectories were
already evaluated in EXP-0009: these are new observations of acquired behavior, not fresh
world dynamics or final confirmation. Final trajectories remain unrendered.

All three old parents still predict 608/608 old-view development trajectories, all 1,920
prefixes and 64/64 own-state continuation pairs before adaptation. Their zero-shot one-step
training and validation correctness is zero under both new views. The original snapshots
remain byte-identical after the study. Keeping an immutable old version preserves its
competence; it does not demonstrate learning without interference in shared changing weights.

## Acquisition and subsequent competence

All 24 one-step fits complete before any mixed fit. An arm/view advances only when every
seed passes and replays. A selected acquisition checkpoint must pass 98% training and 95%
validation trajectory correctness, the 90% action/length floors and reconstruction floors.
Correctness requires every decoded coordinate at every prefix to be within 0.25.

| View | Operation treatment / mapping initialization | One-step acquisition | Mixed acquisition | Development competence |
| --- | --- | ---: | ---: | ---: |
| Translation | Frozen / retained | 3/3 | 3/3 | 1/3 |
| Translation | Frozen / reset | 2/3 | Not admitted | Not admitted |
| Translation | Refit / retained | 3/3 | 3/3 | 3/3 |
| Translation | Refit / reset | 3/3 | 3/3 | 3/3 |
| Dense remix | Frozen / retained | 0/3 | Not admitted | Not admitted |
| Dense remix | Frozen / reset | 0/3 | Not admitted | Not admitted |
| Dense remix | Refit / retained | 2/3 | Not admitted | Not admitted |
| Dense remix | Refit / reset | 1/3 | Not admitted | Not admitted |

The nine admitted development evaluations require 95% correct trajectories overall, at
least 90% in every family and 90% successful paired continuations from the model's own state.
The evaluated snapshot is the earliest saved acquisition checkpoint. Later checkpoints
are not evaluated to rescue a failed result.

| Translation arm | Seed | Correct trajectories / 608 | Correct prefixes / 1,920 | Continuation pairs / 64 | All competence gates |
| --- | ---: | ---: | ---: | ---: | --- |
| Frozen / retained | 14003 | 596 | 1,904 | 53 | Fail |
| Frozen / retained | 14009 | 600 | 1,910 | 63 | Pass |
| Frozen / retained | 14027 | 574 | 1,880 | 52 | Fail |
| Refit / retained | 14003 | 591 | 1,903 | 61 | Pass |
| Refit / retained | 14009 | 603 | 1,915 | 64 | Pass |
| Refit / retained | 14027 | 599 | 1,910 | 62 | Pass |
| Refit / reset | 14003 | 608 | 1,920 | 63 | Pass |
| Refit / reset | 14009 | 599 | 1,909 | 60 | Pass |
| Refit / reset | 14027 | 604 | 1,916 | 58 | Pass |

The first frozen failure is continuation alone. Seed 14027 also misses the overall and
length-six family floors. Thus successful short acquisition does not ensure continued
behavior after different histories. Every reconstruction measurement still passes, so
reconstruction preservation is not a sufficient competence test.

Erasing the initial observation reduces all nine models to 0/608 correct trajectories;
erasing state after history reduces every model to 0/64 successful continuation pairs.
Reversing actions leaves only 165–166/608 trajectories correct. Resetting from the supplied
true current observation yields 61/63/59 successful pairs for the frozen retained arm,
63/64/64 for refit retained and 64/64/63 for refit reset, in seed order. This is an assisted
diagnostic with information unavailable to normal continuation. All nine saved-state checks
reproduce eight sampled continuations exactly after reopening.

## Work, integrity and recovery

Cumulative selected one-step plus mixed gradient updates are 256/128/256 for frozen
retained, 256/192/512 for refit retained and 2,048/2,048/2,048 for refit reset. These are
acquisition-point measurements. Every admitted fit completes its full duration: each of
those three translation arms actually consumes 18,432 updates across its six fits.
The protocol's cost-benefit comparison requires competence in every frozen and from-scratch
seed; that prerequisite fails. Earlier acquisition alone does not earn the comparison.
The retained-mapping refit result supports a narrow initialization effect, not reuse of
unchanged operation coefficients or an actual campaign speedup.

All 33 fits, nine evaluations and three parent baselines fully replay. Fit replay recomputes
279 saved measurements and their selection decisions; all 558 train/validation reconstruction
measurements have accuracy 1.0, with maximum coordinate error 1.53e-6. Frozen arms check
operation equality after every update and at saved checkpoints. The 18 refit fits contain
1,938 scheduled refits and 7,752 action systems, all rank 11. Maximum condition number is
97.27 and maximum normalized normal-equation residual is 7.29e-15. No fallback solver or
replacement seed is used. An independent raw-evidence audit finds no discrepancy in
ordinary attempt coverage, selection, metrics or cost totals.

Eight further replays pass using restored artifact bytes and archived source. The 100
attempts comprise 33 fits, nine evaluations, three baselines, 53 replays, one synthetic
preflight and one expected post-fit verification failure. The latter preserves its completed
eight updates separately from failed verification. All ten one-step acquisition failures
remain failures; execution success does not upgrade their scientific outcome.

All attempts together record 116,808 gradient updates, 1,457,324 example presentations,
1,836,380 forward prefixes, 7,955,524 auxiliary observation presentations, 2,150,224 affine-fit
examples and 16,812 linear systems. Recorded process time is 633.48 seconds, maximum worker
RSS is 330,989,568 bytes, and charged run storage is 201,179,136 bytes (188,979,336 logical
bytes). Observation-generation work is recorded separately from model arithmetic. The
injected failure lacks a returned supervisor sample summary but retains worker high-water
RSS and elapsed time. All registered work and storage ceilings are respected.

The entire upstream EXP-0009 campaign is charged once as shared acquisition: 55,336 updates,
310.52 recorded seconds and 72,114,176 charged run bytes. Together the two campaigns consume
172,144 updates, 944.00 recorded seconds and 273,293,312 charged run bytes. These totals
exclude archive I/O, unit tests, report construction and earlier research; they are not
whole-program costs or controlled timing comparisons. The evidence separately retains
batch wall times, solver work and each selected checkpoint's measured exposure and arithmetic.

The private archive includes all 92 ordinary attempts and committed source. All 3,624
entries, totaling 188,743,755 logical payload bytes, restore and hash-verify; the extracted
211 source files also match. Archive SHA-256 is
`7d2be1e2f404fd6e8250cfb4e7a1472103e701212041a5b00dbc4a702e377376`.
The eight recovery outputs and adapter have separately verified private copies. This uses
the existing numerical environment and owner-selected same-disk backup destination. It is
not an independent failure domain, and no unique artifact is retired. Parameter snapshots
support inference replay, not exact Adam continuation.

The default suite reports 248 passed and 19 optional tensor tests skipped. All six new
optional tensor checks pass in focused executions in the admitted environment; the 13
unchanged optional tests from prior studies were not rerun for this item. Rust's 42 tests,
formatting, Clippy and fixture pass. Contracts, host admission and the refreshed EXP-0001
replay of 12,096 predictions pass. Frozen-source Linux/macOS Python and Rust checks pass in
[run 36791914732](https://github.com/depsilon/noetloom/actions/runs/36791914732).
The evidence closure is followed through CI for its exact commit.

## Disposition

Close N-014 at its declared limits. Retain EXP-0009's scoped acquisition recipe as a
development reference and preserve this negative bridge result. H-003 and H-011 remain
proposed; neither is promoted by a frozen-operation reuse claim. No new objective, width,
rate, seed, final-data selection or provider change is admitted here.

The immediate unresolved question is why acquired one-step and short-rollout behavior
fails continuation after histories under even a representable observation translation.
A next study needs a separate queue decision and a falsifiable design that distinguishes
trajectory robustness from acquisition-checkpoint selection, while keeping a competent
control. Dense-remix capacity remains a distinct uncertainty. Changed dynamics, partial
observation, interference under bounded shared storage and physical-provider integration
remain later questions. The requested acquisition and representation-bridge sequence is
complete; no additional campaign is selected by this closure.
