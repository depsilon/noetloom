# 0004 — Reject the first hard-selection configuration

Date: 2026-09-30. EXP-0002 is complete; N-002 awaits hosted delivery checks.

## Decision

Reject the registered selective-read configuration for progression. Retain the implementation,
all seeds, and the negative result. The learned selector reduced payload reads but did not meet
the preregistered accuracy, reliability, or paired-seed comparison criteria. This result does
not reject learned memory generally, establish a new architecture, or justify scaling this
configuration until it wins. H-001 remains an open mechanism question.

The [protocol and design](../../experiments/EXP-0002/design.md) were committed in
`572f2fc4eb8c6beb866d981458526f368fc19141` before preflight or fitting. That immutable revision
contains the exact learning source for replay. A later doctor-message correction describes
its actual inspection scope; it changes the broad Python source inventory but no learning
computation. The [compact evidence](../evidence/N-002-2026-09-30.json) binds the experiment to
its original source, binary, inputs, initial/selected checkpoints, reports, and replay records.

## Result

Each arm used five independent training seeds, the same initialized parameter allocation,
training data/order per seed, 256 Adam steps, three validation opportunities, and 2,048 final
queries across four frozen families. Ablations freeze or disable the relevant parameters.
No failed training attempt was replaced. All 20 execution runs completed and were replayed.

| Arm | All families | Base/unseen keys | Longer delay | Larger working set | New update composition |
| --- | ---: | ---: | ---: | ---: | ---: |
| Selective learned read | 72.63% | 76.33% | 70.74% | 70.20% | 73.24% |
| Dense learned read | 84.90% | 89.38% | 82.03% | 81.91% | 86.29% |
| Frozen routing | 23.19% | 23.67% | 23.52% | 22.70% | 22.89% |
| No history | 25.00% | 25.00% | 25.00% | 25.00% | 25.00% |

Selective per-seed accuracy was 83.11%, 85.21%, **25.59%**, 84.62%, and 84.62%. The third
seed is retained. Dense accuracy ranged from 82.23% to 85.94%. The paired selective-minus-dense
mean was −12.28 percentage points, with a 95% t interval of [−45.22, +20.67] points across
the five training seeds. This is not evidence of a universally superior baseline; it fails
the registered −5-point noninferiority bound. The ablation effect lower bounds were also
below the required +20 points. Only the payload-read criterion passed.

Every selective run read 65,536 payload bytes for its final queries; dense read 927,744,
a ratio of 0.07064. Both scanned 1,508,864 logical descriptor bytes for routing and traversed
another 3,627,008 descriptor bytes during state validation. Both wrote 133,120 event-payload
bytes; null-state initialization is reported separately. This is sparse payload access,
not sublinear search or a total-memory saving. Median native process observations were
20.49 ms selective and 20.17 ms dense for 2,048 queries, including process/input/output
overhead. These five observations do not establish a speed advantage. No speed claim is made.

## Verification and resource scope

The CPU-only preflight checked numerical dense gradients (maximum error about 2.44e-11),
all four arms' exported parameter parity, and throughput using separate development keys.
It selected the largest registered count, 256 steps, without using quality to select the
method. Release compilation took about 7.3 seconds; preflight's worker took about 2.8 seconds.
The backend was PyTorch 2.14.0, float32, one thread, deterministic algorithms; native inference
was the Rust resident provider with versioned transactions and a fixed experimental controller.

Every run reloaded its selected JSON parameters, checked all final logits/classes against
Rust, executed a state prefix using the persistent provider, and resumed in a separate
process. A further fresh Rust replay rechecked 2,048 predictions and deterministic operation
counts per run: 40,960 independently replayed predictions in total. The scorer regenerated
the frozen data and independently checked mutable binding semantics. Checksums and replay
do not independently attest historical optimization, wall time, or authorship.

Peak worker RSS stayed below 322 MiB. Each run used 9,736 query presentations, below its
10,000 ceiling. Full training artifacts occupy about 28.6 MiB; all setup/preflight/training/
verification/summary evidence occupies about 52.4 MiB at this recording. They remain in the
unsynced local cache and are not publicly retrievable from their manifests alone. Initial,
all validation checkpoints, selected weights, failures, raw predictions, and source identities
are retained. No unique checkpoint was deleted and no weight license or publication was assumed.

Two dependency-setup attempts stopped at the storage monitor before training: pip's installed
staging was initially misclassified as downloads, then a two-pass live-directory scan raced
file growth. Single-pass classification corrected the monitor without raising limits. Only
reproducible incomplete installation staging was deliberately discarded, with its identities
recorded; verified wheels and both failure records were retained. The final installation used
about 575 MiB plus 131 MiB retained downloads within the original 1 GiB/256 MiB reservations.

Local completion checks: 68 Python tests; 30 Rust tests, formatting and Clippy; repository
contracts; a refreshed foundation restart; and 12,096 EXP-0001 predictions replayed under
the final Python source. Hosted verification will be linked below when complete.

## Next technical choice

The measured limitation is unreliable hard selection, not a demonstrated shortage of model
width or available storage. The learned dense control is a useful comparison component; it
does not become Noetloom's foundation. N-003 should register a bounded test of whether a
learned compute-allocation decision can preserve dense-read quality while selectively
reducing payload work. Compare against fixed sparse and fixed dense policies, charge the
decision and failed sparse attempts, and use new held-out examples because EXP-0002's test
results have now informed that design. Do not claim procedural reuse from such a test.

The broader representation horizon remains open. No cognitive category inventory, external
pretrained model, or mandatory ShardLoom representation was introduced.

## Hosted verification

Pending the experiment delivery commit. N-002 remains active until both hosted jobs pass.
