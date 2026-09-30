# EXP-0005 — Acquisition before transformation claims

This executes N-007's development calibration. EXP-0004 remains immutable. The scientific
comparator is a competent own-initialized learned control, with measured fitting and
generalization; a successful execution preflight is insufficient.

## Task and information

Six anonymous entities have a strict order. A query marks two entities; predict whether the
first precedes the second. Each entity occupies an eight-number row: six observation cells,
a signed query marker, and a surface marker. Ranks put the normalized rank in cell zero;
sequence puts a one in the rank column; relations contain signed comparisons to entities.
Two unused rows carry asymmetric orientation marks. The full observation is 64 scalars.
An independent decoder checks the observed grammar against latent labels. It is never
called by a model. Equal class support is constructed at the latent-problem level.

This deliberately supplies entity rows and format information. It is easier than EXP-0004
and cannot rescue its result. The six-entity grammar is disjoint from its retired five-entity
grammar. Split latent order/query pairs by their six-member relabeling orbit before rendering
multiple views, preventing the registered row permutation from crossing partitions. Development training,
validation, transfer, and reserved confirmation problems have disjoint latent keys and actual
inputs. A development command must not render or score reserved confirmation inputs.

The three formats share training latent problems, so this is disclosed multi-view experience
with answer labels, not independent observations or auxiliary canonical-state supervision.
The one-format stage uses ranks alone. The mixed stage uses all three, with equal support.

## Limited models

All parameters start from seeded random initialization and use tanh MLPs and Adam on one CPU
thread. No pretrained component, teacher, hand-written answer computation, optimizer-resume
claim or foundation-architecture adoption is involved.

- `shared_rows`: the same learned 8→32→16 transform reads each of the six entity rows;
  their sum enters a learned 16→32→2 solver. Entity locality and summation are supplied
  relational biases, not discovered invariance. It ignores the two orientation-marker rows.
- `transport`: a 64→16→1024 network produces sixteen row-softmax averages of the complete
  field; a 16→32→32→2 solver receives only those averages. This probes the earlier bottleneck
  on an easier task; it does not retroactively change EXP-0004.
- `bypass`: the same transport construction, followed by the same solver widths, with the
  raw 64 scalars concatenated to its sixteen averages. Its extra access, parameters and work
  are charged. An advantage could reflect optimization or capacity, not only information loss.

Report parameter counts, forward operation estimates, measured fitting/replay cost, input and
artifact bytes, intermediate variation and a constant-intermediate intervention. The latter
is a dependence diagnostic, not semantic interpretability or a proof of representation collapse.

## Development search and stages

The JSON protocol fixes two conditions, three seeds, three arms and three stages. Run all
three seeds for the short condition; if any seed misses the stage gate, try all three with
the long condition. Select the first condition passing every seed. A model that fails both
conditions stops at that stage. Other models can continue independently. No failed attempt
is retried under the same identity. Any implementation failure is retained and consumes its
attempt; it cannot be substituted with a favorable seed. No third condition is admitted.

Each stage trains from initialization, not from a selected preceding checkpoint. Tiny fits
32 problems and selects by training loss. Single uses 384 rank problems; mixed uses 384
problems in each format. Validation has 96 fresh problems per format. All measured training
examples and validation examples are evaluated at five fixed points, including initialization.
The selection rule is lowest validation loss, then earliest step. Gates apply to the selected
snapshot and every seed; mixed gates apply separately to every format. Preserve minibatch
losses as well as these measured curves. Initial metrics cannot count as learned acquisition.

Only models passing mixed acquisition enter development transfer: new problems under a row
permutation (relation columns co-permute) or a whole-field transpose. The first probes a
supplied bias; the second changes the observation layout beyond training. These are diagnostics
on development data, not unbiased final results and not new semantic task structures.

## Admission and confirmation boundary

`local-calibration` keeps the 10 GiB cache, 20 GiB disk headroom, 120-second worker and
2 GiB sampled-RSS ceiling. It explicitly admits up to 50,000 presentations per run so that
the long condition can test acquisition; the original `local-small` profile remains unchanged.
At most 54 development fits, 15 possible confirmation fits, two execution preflights and one
post-fit failure injection are admitted, with a total 1.125 GiB
of retained artifacts across fitting and replay. Up to 69 replays are admitted, with a combined
four-hour worker ceiling. Actual use, failed work and monitoring overhead are reported.
Preflight can refuse infeasible conditions; it cannot reduce them and silently claim the
planned acquisition test ran. Serialization and strict final byte accounting remain required.

Before any new learned snapshots are retained, verify the owner's selected private local
copy of prior unique artifacts and an isolated restore/replay. The owner selected this
same-disk destination after the independent-destination requirement was surfaced;
[recovery evidence](../../docs/evidence/N-007-recovery.json) records the narrower protection.

If no model passes, localize the earliest failure and close calibration. If a baseline passes,
freeze a separate confirmation record and fresh training seeds before rendering final inputs.
It must specify the selected condition per arm, sample/gate rules, paired-seed comparisons
when justified, transfer margins, missing runs and total cost. Only acquired arms may enter
that comparison; a baseline-only competence confirmation is permissible and cannot claim
the transport mechanism wins. Final results never select another condition.

## Recovery and verification

Publish each curve point atomically and a completed `fit.json` before downstream checks.
Fitting, verification and resource status are separate; absent records mean unknown or
interrupted. A deliberately injected post-fit error must preserve the fit and snapshots while
leaving the overall run failed. Parameter files support inference only.

Use an independent scalar forward implementation for numerical checks and a fresh process
for replay of all saved predictions and independently recomputed scores. This calibration uses
the existing numerical environment, without extending the Rust runtime. A replay validates
saved inference, not a reproduction of stochastic optimization. Restore and replay selected
new evidence from its second copy before delivery, and retain all attempts.
