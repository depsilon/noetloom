# 0006 — Task acquisition did not establish a representation result

Date: 2026-09-30. EXP-0004 and N-006 are complete, with an inconclusive research outcome.

## Decision

Reject the registered configuration and classify the H-011 comparison as **inconclusive
because task acquisition failed**. The conditional model averaged 58.54% accuracy on familiar
forms and 48.61% on held-out transformations. Every control also stayed below the registered
70% familiar-form acquisition floor. The setup did not acquire the task adequately enough
to discriminate useful representation strategies. This does not falsify H-011.

There is a separate execution limitation: nineteen of twenty attempts completed normal
verification. One larger-control attempt was interrupted after fitting by a filesystem
accounting race. A later audit verified its saved predictions and six retained states, but
did not restore its failed status. No seed was replaced or fitting repeated. The normal
driver correctly refused to issue a complete-campaign summary.

H-011 stays open. H-001/H-002 remain dormant. This result does not earn progression to learned
reusable computation, and no follow-on experiment is added to the queue.

## What was registered

The [design](../../experiments/EXP-0004/design.md) and strict protocol were registered in
`f2be285`; executable source was committed before preflight or fitting in
`293a9578f9ed5a700be3d4d6e43a7308d1fbe598`. The
[compact evidence](../evidence/N-006-2026-09-30.json) preserves all twenty attempts, checkpoint
and source identities, the failed attempt, the later audit, and the subsequent repairs.

Each problem asks whether one of five anonymous entities precedes another in a total order.
Numeric ranks, sequence permutation matrices and signed pairwise relations render that
relationship in an 8×8 numeric field. Training exposes one view per problem, without paired
views or canonical intermediate targets. Models receive only 64 raw values. An independent
scorer decodes the rendered field and checks the latent answer.

There are 768 training, 96 validation and 32 development problems. Four final families have
96 problems each: familiar surface/rotation pairs, unseen combinations, reflections, and
reflected unseen combinations. A separate 96-problem diagnostic uses all three views.
Latent keys and actual input hashes are disjoint across partitions. All surface grammars
appear during training; this tests transformations and combinations, not unseen modalities.

C learns a dense 16×64 row-normalized transport matrix for each input and solves from sixteen
transported scalars. Controls are smaller and larger fixed-layout networks, plus learned
input-independent transport with the same solver capacity. Every arm learns hidden features.
The field, intermediate width, operators and objective remain designed constraints; this is
not unrestricted representation discovery or a final foundation architecture.

## Retained-checkpoint observations

Each row averages all five selected checkpoints. Transfer averages the three transformation
families equally. The interrupted B checkpoint is explicitly included through its later audit.

| Arm | Familiar forms | New combinations | Reflections | Joint transforms | Transfer mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| A: smaller fixed layout | 58.96% | 47.50% | 52.29% | 51.04% | 50.28% |
| B: larger fixed layout¹ | 58.96% | 50.42% | 55.21% | 52.50% | 52.71% |
| C: conditional transport | 58.54% | 45.83% | 47.08% | 52.92% | 48.61% |
| S: static transport | 52.29% | 48.96% | 50.00% | 50.42% | 49.79% |

¹ B/6503 has reproducible saved predictions but lacks complete-run admission and a final report.
The other four B runs average 59.38% on familiar forms, also below the acquisition floor.
The audit neither excludes that seed nor replaces its training attempt.

C's transfer scores range from 45.49% to 51.74%, all below the 60% per-seed floor. Its
three-surface prediction agreement is 34.17%, below the required 80%. C minus the intervention
that shifts transport maps between examples averages −2.85 percentage points, with a paired-seed
95% t interval of [−9.43, +3.74] points. There is no registered beneficial-dependence effect.

Descriptive C-minus-control transfer differences are −1.67 points versus A, −4.10 versus B,
and −1.18 versus S, with intervals [−5.20, +1.87], [−5.81, −2.39], and [−5.00, +2.63].
The B interval includes the audited failed checkpoint. These describe retained predictions;
the incomplete campaign cannot supply a successful registered comparison. Five initialization
seeds on one frozen dataset also do not estimate uncertainty over arbitrary task families.
Weak acquisition limits interpretation independently of the execution failure.

## Learning and costs

A development-only preflight admitted 1,024 Adam updates of six examples per arm, paired
minibatch indices, and validation at 256, 512 and 1,024 updates. Earliest minimum validation
cross entropy selected the checkpoint. All twenty attempts reached a saved step-1,024
checkpoint. No final score changed the settings. All parameters were initialized by the
project, without inherited models, teachers, external examples or pretrained embeddings.

| Arm | Trainable scalars | Nominal forward work | Registered fitting proxy |
| --- | ---: | ---: | ---: |
| A | 3,202 | 6,402 | 150,790,144 |
| B | 36,482 | 72,962 | 1,718,411,264 |
| C | 20,114 | 46,354 | 1,060,364,288 |
| S | 2,690 | 10,482 | 220,749,824 |

Equal learning opportunities do not imply equal realized computation: B exceeds C in capacity
and nominal work. The fitting proxy charges three forward counts per training presentation
plus ten operations per parameter per Adam step; it is not measured hardware FLOPs.
Validation, construction/conversion, intervention and replay work are separately recorded.
Full process timings include startup, state access, validation, hashing and serialization.
No speed or efficiency advantage is established.

Admissions were 120 seconds, 32 MiB output and 2 GiB sampled process-group RSS per run.
The nineteen complete workers peaked at about 310.4 MiB. The failed worker's final RSS,
timing and complete work record are unknown, not zero. About 105.6 MiB of representation
artifacts remain locally, including 56.5 MiB for the twenty attempt directories. All initial,
validation and selected checkpoints, raw outputs, the immutable executable, failure and audit
are retained. Nothing unique was deleted or released publicly; no durable remote backup is claimed.

## Failure, audit and repair

B/6503 failed while publishing intermediate state for case 288. The supervisor enumerated
`.CURRENT-32651-2`; Rust atomically renamed it to `CURRENT`; the supervisor's subsequent
`lstat` raised `FileNotFoundError` and stopped the worker. A deterministic filesystem fixture
reproduced this sequence before final quality was inspected.

A separate bounded audit replayed 966 case executions without training or changing the failed
directory. Native validation losses were 0.72582, 0.76066 and 0.81022, confirming the saved
step-256 selection. Six completed original intermediate states reopened correctly. Cases 288
and 289 lack complete original restart evidence. The audit did not manufacture replacement
states, final resource measurements or a successful training manifest.

Repair `30534e77fb87ebb9e5bff9053a69dd870626b1b6` tolerates disappearing entries only in live
sampling and requires strict output/workspace inventories after worker exit. Symlinks,
special files and other I/O failures remain errors. CI then exposed the same race in Cargo's
temporary build directory. Repair `e11d80b53490c67e9341de5b2d6e8e1048e9b525` applies the live/strict
distinction to that sampler. Regression tests cover actual atomic rename, unsafe entries,
strict completion, and both supervisor paths. No experiment was rerun after either repair.

## Verification and boundary

Preflight checked 29 sampled derivatives across all conditional parameter tensors, with
maximum error 1.34e−11, and both inference paths refused label-bearing fields. Maximum final
native/tensor discrepancy was 1.20e−6, below 2e−4. Nineteen normal replays executed 20,312
cases; the audit added 966. Together these cover 15,360 ordinary/diagnostic/intervention
predictions, 5,760 validation executions and 158 retained-state resumes. They are repeated
verification executions, not 21,278 independent learning examples. Two original resumes
remain missing. Replay does not independently repeat fitting or attest historical timings.

Local verification passes 111 Python tests, 42 Rust tests, formatting, Clippy, repository
contracts, a fresh foundation restart and 12,096 EXP-0001 replayed predictions. Historical
EXP-0004 replay requires original commit `293a957` and retained artifacts; repaired source
is not relabeled as the code that produced the experiment.

Any later protocol must establish informative acquisition without using these final examples
to choose a favorable method. Further optimization, learned reuse and other horizon work need
a separate queue decision. H-011 and the charter remain unresolved.

Both Linux/Python 3.11 and macOS/Python 3.13 passed for repaired implementation
`e11d80b53490c67e9341de5b2d6e8e1048e9b525` in
[Checks run 36713616561](https://github.com/depsilon/noetloom/actions/runs/36713616561).
Hosted checks cover contracts, native fixtures and harness replay; they do not repeat training.
