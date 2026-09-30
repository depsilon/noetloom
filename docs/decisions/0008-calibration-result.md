# 0008 — Learning is observable; reliable mixed-format acquisition is not confirmed

Interpretation correction, 2026-09-30: [decision 0009](0009-input-validity-and-next-study.md)
shows that the shared-row transpose path omits the query, and ranks/sequence holdouts reuse
training patterns under its supplied symmetry. The scores and failed confirmation below
remain historical facts; their transfer interpretation is narrowed by that correction.

Date: 2026-09-30. N-007 / EXP-0005 is complete with a localized calibration failure.
The five-seed confirmation did **not** pass. Four fresh seeds met every acquisition gate;
seed 8209 reached 89.32% rank-format training accuracy against the registered 90% floor.
Its final partition was not evaluated. No seed was replaced, no fitting was repeated, and
no setting was changed after final evaluation began.

The implementation and evidence are useful: every model learned the tiny and single-format
tasks, fitting records survive downstream failure, and all 41 non-injected fits replayed.
This does not establish a reliably competent mixed-format baseline, a transport advantage,
or a Noetloom foundation architecture. H-011 stays open; H-001/H-002 remain dormant.

## Registration and learning opportunity

The owner authorized execution after the [method revision](0007-acquisition-calibration.md).
The [pilot](../../experiments/EXP-0005/protocol.json) and implementation were committed and
pushed as `734e3d618a1e0ba7be655e7a57b3c668268040ac` before fitting. The six-entity task exposes
64 numeric values with entity rows and format markers. It is an easier, explicitly supplied
representation than EXP-0004, whose task, artifacts and conclusion remain unchanged.

Three own-initialized models received the same latent problems, answer labels and declared
training choices: a shared entity-row transform, conditional averaging, and averaging with
a raw-input bypass. There was no pretrained component, auxiliary teacher or runtime decoder.
The exact decoder remained in generation/scoring. The models do not test persistent memory,
learned recurrence, procedure consolidation or language.

The 36 development fits cover three seeds per attempted condition. All three models passed
tiny-set fitting and fresh rank-format generalization under the short condition. None passed
the complete three-seed mixed-format gate under the original minimum-validation-loss rule.
Transport and bypass had substantial mixed-format validation deficits even when training
accuracy was high. The bypass did not resolve them; these results do not isolate averaging
as the cause or prove representation collapse.

The shared-row control's final 2048-update snapshots passed all three development seeds.
For seed 7103, minimum validation loss instead selected step 512, whose relation training
accuracy was only 86.72%. We retained that original failure and registered **one explicit,
development-informed checkpoint-selection amendment**, choosing the final snapshot.
It expanded the selection opportunity and was not part of the original preregistration.
The [amendment](../../experiments/EXP-0005/confirmation-amendment.md), parent artifacts,
five new seeds, gates and implementation were frozen in
`e1db2593f87fd4a555c2727bc504bc25f5cd7ae4` before final inputs were rendered or scored.

## Confirmation and failure localization

The 1,426-parameter control trained for 2,048 updates with the frozen long condition.
Each format has 384 training and 96 validation cases. Final evaluation uses 192 reserved
latent problems in three formats and three layouts. Partitions separate relabeling orbits;
actual rendered inputs are also checked for overlap. Fresh seeds measure training variation,
not new task structures or a population sample.

| Seed | Minimum training accuracy | Minimum validation accuracy | Acquisition | Final canonical | Final row permutation | Final transpose |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| 8101 | 96.88% | 89.58% | Pass | 96.70% | 96.70% | 50.17% |
| 8209 | **89.32%** | 85.42% | Fail | Not evaluated | Not evaluated | Not evaluated |
| 8311 | 97.14% | 88.54% | Pass | 97.74% | 95.49% | 48.96% |
| 8419 | 98.70% | 86.46% | Pass | 97.22% | 96.53% | 49.13% |
| 8521 | 98.70% | 93.75% | Pass | 97.05% | 97.57% | 49.48% |

Training and validation minima are across formats. Final columns average the three formats
within each seed; they describe the **conditionally evaluated four-seed subset**. They are
not a five-seed competence or transfer result. The untrained control scored 50.00–51.39%
on canonical cases in that subset. No registered five-seed interval or retention decision
is reported when one seed fails admission. Transposition remains near chance in every
evaluated seed; the strong canonical scores do not imply layout-independent competence.

Seed 8209 had passed acquisition at step 512, then lost rank accuracy by the frozen final
step. Its validation loss rose from 0.11168 to 0.37723. This localizes a training/selection
stability problem rather than absence of all learning. Selecting that earlier checkpoint
now would respond to confirmation evidence, so it was not substituted or evaluated on final
cases. A future stability study needs a new bounded decision and fresh final data; this
partition is retired from future confirmatory model selection.

## Deviations, verification and recovery

The original pilot evaluated development transformations for three individually passing
seeds before their whole condition qualified. Those observations did not enter fitting,
checkpoint selection or short/long choice. They remain disclosed exploratory records, with
no arm-level transfer comparison. The corrected driver admits that action separately and
requires the complete registered seed group. No historical run was rewritten by the repair.

Fitting telemetry is published before verification. The registered injected post-fit failure
preserved its five measurements and snapshots while the run remained failed. Final decisions
now require successful fitting, verification, resource admission and matching replay evidence.
Summaries validate historical source revisions without weakening execution's source checks.
Independent scalar checks supplement fresh-process replay of saved curves and predictions;
replay does not reproduce stochastic optimization or provide exact optimizer continuation.

The ledger contains 85 attempts: 36 development fits, five confirmation fits, 41 replays,
two preflights and one expected failure injection. It charges 42,648 updates, 1,262,416
case presentations and 277.83 seconds of supervised worker time. Separate restore checks
and storage copies are recorded in the [compact evidence](../evidence/N-007-2026-09-30.json).
These are measured scopes, not an efficiency comparison or whole-machine resource audit.
Recovery checks add 62,736 measured presentations; repeats repair incomplete resource receipts.
An interpreter mismatch failed before numerical initialization and was retained. Charging that
attempt conservatively still leaves the study below every registered aggregate ceiling.

Prior learned artifacts were copied and restored before new fitting. The complete campaign
was then copied to the owner's private local backup, with all 1,159 archived files checked
after restoration and acquired/failed confirmation samples replayed from restored bytes.
The archive is 34,333,946 bytes, SHA-256
`ccbfeb09f766e03634078457bdc03b35dc34c1aa15244bb96079a130dfd5508f`.
The Desktop link points outside Desktop sync to `~/Noetloom-Private-Backups`.
This protects against loss of a working copy, not physical disk failure. Nothing was uploaded
or deleted; inference parameter snapshots remain distinct from resumable training state.

All 127 Python tests, repository contracts, skill validation and refreshed EXP-0001 replay
pass. Hosted Linux/macOS checks passed for both the pilot and frozen confirmation commits;
delivery of this decision follows the same checks. Rust source is unchanged; hosted checks
cover its tests, formatting, Clippy and fixture. Bulk evidence stays private and outside Git.

## Queue decision

Close N-007 at its registered boundary. Retain the working calibration/recovery machinery and
all results, without promoting the unreliable configuration. N-008/N-009 remain conditional
directions, with no automatic execution. The remaining prerequisite is reproducible learned
acquisition under a separately admitted stability-calibration protocol. No further fitting,
larger model, learned halting, runtime rewrite or deeper ShardLoom integration follows from
this result.
