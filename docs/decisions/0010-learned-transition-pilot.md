# Learned transition pilot: retain the component result, revise the comparison

Date: 2026-09-30. Work item: N-008. Experiment: EXP-0006.

The 288-parameter shared-transition probe acquired every registered development stage
in all three seeds and predicted all 608 development-transfer trajectories exactly per seed.
The 14,536-parameter recurrent control acquired the one-step task and fitted the short-sequence
training set, but failed short-sequence validation at both permitted learning rates. The
registered baseline prerequisite therefore prevents a five-seed confirmatory comparison.
Final trajectories remain unrendered; no further tuning is admitted under this protocol.

Retain the narrow finding that learned action-conditioned transitions can be reused in this
finite task with supplied observation-aligned state. Do not promote H-003's cost/transfer
hypothesis, claim a confirmed advantage over a competent control, or adopt this probe as
Noetloom's foundation. Select N-011 to test the dependence on the supplied state representation.

## What ran

Source, protocol and implementation were frozen in
[`1eeda57e868fad0d3608c4f0cd30b93c0ba1e513`](https://github.com/depsilon/noetloom/commit/1eeda57e868fad0d3608c4f0cd30b93c0ba1e513)
before fitting. The [registered design](../../experiments/EXP-0006/design.md) and
[protocol](../../experiments/EXP-0006/protocol.json) remain unchanged. The canonical saved
protocol SHA-256 is `1587227774be42c71dfbb176b4f9132286593c02491e466af1ce5e1e66b9c15d`;
the source file has a different byte hash because its formatting differs from the saved copy.
[Machine-readable evidence](../evidence/N-008-2026-09-30.json) records all attempt identities,
selected metrics, learning curves, controls, costs and recovery receipts.

One synthetic world has eight observed bits and four anonymous actions, each a fixed coordinate
permutation plus an XOR mask. Both own-initialized models receive the full starting state and
ordered actions. Both train against every prefix outcome, run from their own prior states,
and receive the same minibatches for a seed. Stages restart from fresh parameters. Neither
model receives simulator transitions or intermediate observations during inference.

The candidate's eight-dimensional state aligns with the observed bits, and each action selects
a learned matrix and bias. The control encodes the starting state into a 64-dimensional GRU
hidden state and decodes its predictions. Both recur. The candidate's coordinate alignment
and action-specific parameter bank closely match the environmental algebra; these are supplied
biases, not learned representation discovery or learned selective activation.

Input audits include every observed prefix, exact and latent trajectory overlap, known model
equivalences, and six action-order counterexamples. No cross-partition effective-input or complete
trajectory overlap was found in the audited training/validation/development data. Net-function
exclusions cover every allowed training word and auxiliary prefix, rather than only sampled
training examples. Development six-step words also exclude reserved four-step subwords at every
position. Final function reservations exclude every contiguous development subword. Intermediate
state values can overlap; disjoint starting states do not imply disjoint elementary transitions.

## Acquisition and development transfer

All 24 development fits completed and passed execution verification. Nine failed scientific
acquisition gates and remain in the evidence. An additional deliberate verification failure
retained its completed eight-update fit record as intended.

| Stage | Shared transition | Direct recurrent control |
| --- | --- | --- |
| Tiny fitting, 256 updates | 3/3 acquire at 0.003 | 0/3 at 0.003; 3/3 at 0.01 |
| Fresh one-step inputs, 1,024 updates | 3/3 acquire at 0.003 | 3/3 acquire at 0.003 |
| Short sequences, 2,048 updates | 3/3 acquire at 0.003 | 0/3 at 0.003; 0/3 at 0.01 |

Every acquired selected snapshot scored 100% exact final-state accuracy on its training and
validation data, including required action and length slices. The direct mixed-stage snapshots
also scored 100% on training and one-step validation. Their failures are concentrated in
two- and three-step validation; this is a generalization limitation after successful fitting,
not evidence that the optimizer cannot fit the task or that the input omits the answer-relevant
state. The measurements do not isolate the cause of that limitation.

| Direct condition | Seed | Selected update | Two-step validation | Three-step validation |
| --- | ---: | ---: | ---: | ---: |
| 0.003 | 9103 | 2,048 | 68.75% | 25.00% |
| 0.003 | 9209 | 2,048 | 62.50% | 26.56% |
| 0.003 | 9311 | 2,048 | 75.00% | 31.25% |
| 0.01 | 9103 | 2,048 | 82.81% | 29.69% |
| 0.01 | 9209 | 1,024 | 68.75% | 17.19% |
| 0.01 | 9311 | 2,048 | 78.13% | 40.63% |

Each length has 64 validation trajectories; the exact-state gate is 85%, with additional
95% changed-bit and action-slice requirements. Half the validation set is one-step, so the
aggregate would conceal how poor the longer predictions are. Failed selected snapshots are
minimum-loss diagnostics; none was relabeled as acquired.

The candidate alone qualified for the separately permitted development-transfer evaluation.
Every seed scored 100% exact states and changed bits in every family below. Untrained copies
scored only one or two of 608 cases correctly, all in the one-step family. Copying the initial
state scored zero correct cases. The remaining controls show the importance of action order:

| Development family | Cases per seed | Trained candidate | Exact oracle after sorting actions | Candidate with reversed actions |
| --- | ---: | ---: | ---: | ---: |
| Fresh one-step inputs | 128 | 100% | 100% | 100% |
| Fresh short inputs, familiar words | 128 | 100% | 49.22% | 36.72% |
| Held-out ordered pairs | 64 | 100% | 100% | 0% |
| Unfamiliar four-step compositions | 96 | 100% | 13.54% | 7.29% |
| Four-step words with held-out pairs | 96 | 100% | 33.33% | 1.04% |
| Unfamiliar six-step compositions | 96 | 100% | 8.33% | 4.17% |

These are three initialization seeds in one world using the same finite evaluation set, not
1,824 independent experiments. No population confidence interval or confirmed architecture
effect is claimed. Sorting is insensitive on the two ascending held-out pairs and on one-step
inputs; it is not a diagnostic negative control for those families. Reversal is diagnostic
for the held-out pair family. The exact oracle remains separate from learned model results.

## Cost and recovery

All 59 supervised attempts are charged: 24 development fits, one execution preflight, one
failure injection, 24 ordinary fit replays, three development-transfer evaluations, three full
transfer replays, and three replays from the restored archive. Together they used 26,936 gradient
updates, 671,884 trajectory presentations, 915,455 prefix outputs and 337.23 supervised worker
seconds. Run directories occupied 46,235,648 bytes; the largest observed process-group or worker
high-water RSS was 316,702,720 bytes. Every registered aggregate and per-worker limit was met.
RSS checks are sampled admission controls, not an operating-system memory sandbox.

The counted forward-work proxy is 15,214,622,512 operations across those attempts. Fitting
separately reports a 33,474,461,952-operation training estimate for the 24 development runs,
including estimated backward and Adam work. These overlap and must not be added. They exclude
uncounted host-side simulator, serialization and audit arithmetic; they are not measured FLOPs
or evidence of a wall-clock speedup. Per-run wall time, fitting-loop time, bytes and parameters
remain available in the evidence. The control's extra search is included in realized costs.

All 24 fits replayed every saved measurement and selected prediction in a fresh process; all
three development evaluations replayed their full predictions and controls. Sampled scalar
equations independently checked numerical outputs, and serialized working states continued
exactly. These are parameter snapshots and inference restart checks, not optimizer continuation.

The owner-selected private backup at `~/Noetloom-Private-Backups/N-008-complete-2026-09-30`
contains all 56 original campaign run directories plus the frozen Git source archive. Its
879 archive entries were restored and verified byte-for-byte. The 18,030,835-byte archive has
SHA-256 `7ac3b34b2c77a4fbe1975ff6e0ff863388f2f9598757c709c44d4bf9e8115f23`.
Representative acquired, failed-acquisition and longer-rollout artifacts replayed using the
restored source and weights. Their 37 receipt files and exact recovery recipe have a verified
private copy beside the archive. Directory permissions are 0700 and private files 0600.

This is a second copy on the same physical disk, as selected by the owner. It does not protect
against disk loss. Recovery used the existing local PyTorch dependency, which is not bundled
in the archive; no cross-machine bitwise reproduction is claimed. Nothing was retired or
uploaded, and no raw weights enter Git.

## Decision and next test

Close EXP-0006 as a completed development pilot with a retained component result and an
unqualified comparison baseline. Its conditional confirmation is **not admitted**, so the
five-seed acceptance step is inapplicable under the frozen stop rule rather than silently
waived. H-003 and H-011 remain open; novelty remains unassessed.

Select [N-011 / EXP-0007](../../experiments/EXP-0007/design.md): test whether composition survives
when the model must learn its state encoding and decoding, and separate that burden from
transition sharing and direct observation alignment. A declared reconstruction/state-consistency
objective is a testable aid, with the same observed-prefix information available to controls.
It is not an established explanation of the GRU result. Use a fresh world and partition,
explicit matched controls, sensitive per-family interventions and a new bounded registration.
Do not inspect EXP-0006 final data to design the next study or extend its failed baseline sweep.

Local verification includes all 144 Python tests, repository contracts, doctor, whitespace checks,
and EXP-0001 run `20260930T171300Z-ae85174a80`, which replayed all 12,096 predictions. Frozen-source
[hosted checks](https://github.com/depsilon/noetloom/actions/runs/36748020378) passed on Linux and
macOS, including Rust checks and fixture. Evidence delivery must also pass checks for its exact
pushed commit; the final delivery report records that identity.
