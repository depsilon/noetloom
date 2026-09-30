# 0009 — Correct the input tests and continue toward learned execution

Date: 2026-09-30. The owner requested corrections to the evaluation review and continued
iteration toward an original learned system. This decision closes the evaluation repair
as N-010 and selects the N-008 design brief; N-008's executable registration is its next task.
The numbering preserves the existing N-008/N-009 research directions.

## Two findings reproduced

The [deterministic audit](../../scripts/audit_calibration_inputs.py) reproduces both findings
against the EXP-0005 renderer and shared-row model used at `9ceafec`. It uses no training,
private checkpoints, new learned predictions or parameter selection. Its
[evidence](../evidence/N-010-2026-09-30.json) records the input/source hashes and re-tabulates
the already published per-format scores. Confirmation inputs are inspected retrospectively;
they remain retired from future confirmation.

**Transposition omits the query.** The model takes the first 48 values as six eight-value
rows. Query markers originally occupy column 6; transposition moves them into row 6,
which the learned path never receives. For order `0,1,2,3,4,5`, the opposite questions
`(0,5)` and `(5,0)` have labels 1 and 0. Their transposed fields differ at indices 48
and 53, but their first 48 values are identical in all three formats. This is an
information impossibility for that input path, independent of the fitted weights.

The near-chance transpose scores therefore **do not measure informative reasoning
transfer** for `shared_rows`. Full-field access would distinguish this counterexample;
it would not guarantee that learning succeeds. Historical models, protocols, predictions,
selection decisions and the failed five-seed confirmation are unchanged.

**The supplied symmetry collapses two domains.** Shared row encoding followed by a sum
is invariant to row order in exact arithmetic. Floating-point reduction order can cause
small numeric differences; it does not supply new task structure. For ranks and sequence,
the unordered row collection is determined by two distinct marked ranks: only `6 × 5 = 30`
effective patterns per format. This form has established precedent in
[Deep Sets, sections 2.2 and 3.1](https://arxiv.org/html/1703.06114v3); it is a supplied
architectural bias, not a newly discovered Noetloom procedure.

| Format | Training patterns / 384 cases | Validation cases already represented / 96 | Confirmation cases already represented / 192 |
| --- | ---: | ---: | ---: |
| Ranks | 30 | 96 | 192 |
| Sequence | 30 | 96 | 192 |
| Relations | 384 | 0 | 0 |

Exact full-field observations and the generator's six-member latent relabeling orbits
remain disjoint. The additional overlap appears under the model's wider row symmetry.
This limits the transfer interpretation; it does not erase optimization acquisition or
demonstrate intentional leakage. Zero relation row-multiset overlap is only this specific
check, not proof of new algorithms or independence under every semantic equivalence.

## Separate the useful result from the aggregate

The following are historical canonical scores, with 192 cases per cell. The evaluated
four-seed subset remains conditional on acquisition; no five-seed mean or interval is added.

| Seed | Ranks | Sequence | Relations | Relations after row/column relabeling |
| --- | ---: | ---: | ---: | ---: |
| 8101 | 100% | 100% | 90.10% | 90.10% |
| 8209 | Not evaluated | Not evaluated | Not evaluated | Not evaluated |
| 8311 | 100% | 100% | 93.23% | 86.46% |
| 8419 | 100% | 100% | 91.67% | 89.58% |
| 8521 | 100% | 100% | 91.15% | 92.71% |

Ranks/sequence show acquisition of familiar effective patterns and the supplied row
invariance. The relation scores provide separate within-task evidence on previously unseen
row multisets. They do not establish general reusable computation. Seed 8209's late loss
of acquisition remains a training/selection diagnostic. The short and long conditions
changed both duration and learning rate, so their difference cannot identify either cause.

## Repair and iteration decision

The reusable [input audit](../../noetloom/input_audit.py) counts contradictory targets and
split overlap under an explicitly supplied signature. Its gate rejects answer ambiguity
and rejects known-equivalent holdouts for a transfer claim. Disclosed optimization
calibration may reuse same-target patterns. Regression checks exercise the real transpose
counterexample, reordered observations, multiplicity, cross-split contradictions and missing
holdout coverage. This signature is an evaluation tool, never an input canonicalizer or
answer source for a learner. Future model changes must validate that their audit signatures
still describe their actual input paths.

For historical reproduction, the frozen EXP-0005 implementation is retained. Running
`python3 -B scripts/audit_calibration_inputs.py --require-transfer` deliberately refuses
that configuration. New learning protocols must perform observability and declared
equivalence checks **before fitting**, alongside numerical and resource preflight.
Passing a finite audit establishes only the checked scope.

Do not spend another campaign restoring the static classifier's aggregate score. Carry its
training lesson into **N-008: predictive state and compositional execution**, in
[the next design brief](../../experiments/EXP-0006/design.md). Stabilize one-step and short
sequence acquisition on that task, with a small fixed-duration learning-rate comparison and
checkpoint selection among predeclared acquisition-qualified measurements. Preserve failure
when none qualifies. Freeze fresh confirmation settings only after development selection.

The relevant admission requirement is competence on the next experiment's own task. It does
not require all EXP-0005 formats to become perfect, conditional averaging to win, or a runtime
rewrite. Test new action compositions and useful repeated learned computation with equivalent
information and measured costs. Keep failed trials informative, retire inspected final data,
and select the next bounded revision from what the evidence changes. Originality remains a
research objective, with known components attributed and claims earned separately.

Five focused regression tests and all 132 Python tests pass, along with repository contracts,
doctor, changed skill validation and whitespace checks. Independent counts match the report;
expert review found no actionable defects. The refreshed EXP-0001 run
`20260930T162034Z-ee8129ca86` replayed all 12,096 predictions, with manifest SHA-256
`a93f023747a4e56bd3f566fac2dd098b284bf846bc8db95e645de8de3604cead` and source digest
`99d3a3721f96883438269382b08d7045355588965702c9fd7b370ab7e9a651af`.
These are input/harness checks, not new learning results. Delivery follows the normal hosted
Linux/macOS checks. No fitting campaign was added. The next item's first deliverable is an
executable protocol with concrete tasks, budgets, controls and stopping conditions.
