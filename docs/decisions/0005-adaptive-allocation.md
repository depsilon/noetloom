# 0005 — Reject the allocation gate; retain the simpler control

Date: 2026-09-30. EXP-0003 and N-003 are complete.

## Decision

Reject the registered learned allocation configuration. It preserved quality and reduced
work versus dense reading, but a fixed top-one policy over the same frozen parameters
achieved slightly higher mean accuracy with fewer reads and operations. Three of the five
gates always halted. The preregistered comparison found no meaningful benefit from learning
which queries should continue. Keep every gate checkpoint and the negative result.

The fixed top-one endpoint is a useful diagnostic control for subsequent research. It does
not rescue EXP-0002's rejected hard-selection training configuration: these parameters came
from dense training, and the task examples differ. The result suggests that the training
path deserves scrutiny before adding allocation machinery; it does not identify the cause
of EXP-0002's failed seed. H-002 remains an open hypothesis, with no claim of general adaptive
recurrence, procedural reuse, or a final Noetloom architecture.

The [design](../../experiments/EXP-0003/design.md) was committed before implementation in
`6b46d34`; protocol and executable source were committed before preflight/fitting in
`bd7c1b051fa1621608cdb20b1049e010e7aed216`. The [compact evidence](../evidence/N-003-2026-09-30.json)
records complete source identities, inherited checkpoints, all five attempts, selected and
intermediate gate hashes, native/tensor outputs, restarts, replays, and costs.

## What was tested

Each policy inherited the same five independently trained EXP-0002 dense readers, one per
seed. All 359 parent scalars stayed frozen. Each gate added six initialized weights and a
bias, fitted with a fixed expected-error/payload-cost objective. A development preflight
admitted 128 steps; validation at steps 32, 64 and 128 selected the earliest minimum of the
registered deterministic objective. There was no coefficient, threshold or seed search.

The generator excluded all 5,120 keys from the parent experiment's complete pools. Each
seed used 512 gate-training queries, 256 validation queries and 1,024 test queries across
new bindings, longer delays, a 28-binding working set, and a new delete/reinsert/recover
interleaving. The final test had no role in parameter or checkpoint selection. Inference
refuses label-bearing input fields; the scorer separately computes correctness.

The gate first reads and decodes one payload, then either stops or reads the remainder and
decodes their dense mixture. Continued queries reuse the first payload but still pay for
its decoder and the gate. Fixed top-one/dense controls use the identical inherited weights.
The input-independent random allocator is an analytical mixture of these measured endpoints,
matched to each family's aggregate payload bytes without using correctness to set its rate.
It is not a deployed third implementation or a timing measurement.

## Results

| Policy | All families | New bindings | Longer delay | Larger working set | New interleaving |
| --- | ---: | ---: | ---: | ---: | ---: |
| Learned allocation | 83.79% | 88.59% | 81.72% | 77.58% | 87.27% |
| Fixed top-one | 83.85% | 88.52% | 81.25% | 77.58% | 88.05% |
| Fixed dense | 82.52% | 88.83% | 82.73% | 77.97% | 80.55% |

Adaptive-minus-dense accuracy averaged +1.27 percentage points, with a paired-seed 95% t
interval of [+0.46, +2.08] points. That passes the registered dense noninferiority condition.
Against the equal-payload random allocator, the mean advantage was only +0.077 points,
with interval [−0.055, +0.208] points. Its lower bound does not exceed the required +0.5
points. Three gates never continued; the other two continued on 18.75% and 3.42% of queries.
Only one seed satisfied the 5–95% variable-allocation range required for every seed.

| Native cost, relative to fixed dense | Learned allocation | Fixed top-one |
| --- | ---: | ---: |
| Payload bytes read | 11.20% | 5.86% |
| Total registered nominal scalar work | 89.57% | 77.39% |

All policies scanned the same 921,088 logical descriptor bytes and traversed another
2,567,936 descriptor bytes during state validation per seed. Each wrote 79,872 event-payload
bytes; null initialization is separate. Peak logical payload state was 1,056 bytes and
descriptor state 1,792 bytes. The gate added 235,136 nominal feature/decision operations per
seed, plus extra decoding and mixing on continued queries. These counters cover registered
numerical operations, not every allocator, validation or framework instruction.

Median startup-inclusive native observations were 27.05 ms adaptive, 21.10 ms top-one, and
21.94 ms dense per 1,024 queries. Internal medians were 3.90, 3.55 and 4.43 ms respectively.
One observation per policy/seed cannot establish a stable latency result, and the two timing
scopes differ. No speed claim is made. The fixed endpoint's lower logical cost and comparable
quality are sufficient to reject the added gate in this registered probe.

## Verification and retention

Preflight checked all seven numerical gate derivatives (maximum error about 5.71e-12),
independent tensor/native features and logits, label-field refusal, and both forced gate
branches. Maximum preflight logit discrepancy was about 1.44e-6. CPU training used the
existing PyTorch 2.14.0 installation with one thread and deterministic algorithms; no new
dependency, pretrained model, external data or teacher was introduced.

All five attempts completed on their first execution. Every policy's final logits/classes
matched tensor evaluation, then all **15,360 native predictions** were replayed in fresh
processes with regenerated observations and scoring. The adaptive path also persisted a
prefix and resumed in a separate process for each seed, reproducing all 40 restart queries.
Replay checks exported parents/gates and their execution; it does not independently retrain
the gates or attest historical timings.

Each seed used 9,480 query presentations, below the 10,000 ceiling and 9,488 admitted bound.
The maximum worker high-water RSS was about 313 MiB. All allocation artifacts occupy about
17.1 MiB, including about 9.1 MiB for the five training runs. Initial, all validation and
selected gate checkpoints, parent evidence, native outputs and persistent state remain in
the unsynced cache. The preflight retains its exact executable; EXP-0002's previous executable
was preserved separately before recompilation. Nothing unique was deleted or published as
a weight release. A verified durable remote backup has not been established.

Before fitting, review tightened the final tensor input/scoring separation and corrected a
fixture's expected payload count. No test quality informed those implementation repairs.
Local verification passed 84 Python tests, 36 Rust tests, formatting, Clippy, repository
contracts, a foundation restart and 12,096 EXP-0001 replayed predictions under the current
Python source. Hosted verification is recorded below.

## Boundary for the next research decision

This closes the currently admitted compute-allocation question. It authorizes no extra
training to rescue the gate and no claim that a learned procedure library exists. A next
experiment needs an explicit queue decision and a task where additional learned computation
can produce a benefit that fixed retrieval cannot explain. Training stability and the broader
[representation questions](../architecture/research-program.md#representation-remains-a-research-object)
remain open. Do not equate completion of this queue with achievement of the charter's goal.

## Hosted verification

Both Linux/Python 3.11 and macOS/Python 3.13 jobs passed for delivery commit
`4aba81ebdb61dcb470266cd784650c3a3d66a6f9` in
[Checks run 36701155197](https://github.com/depsilon/noetloom/actions/runs/36701155197).
The jobs include Python tests/contracts, Rust tests/formatting/Clippy, a persistence restart
and harness replay. They do not install the optional trainer or repeat research fitting.
