# Command reference

## Registered learning probe

EXP-0002 has a separate strict `noetloom.learning.v1` contract. The harness `run` command
still refuses learning protocols. See the [design](../../experiments/EXP-0002/design.md)
before executing these commands from the checkout:

```sh
python3 -B scripts/learning_setup.py
python3 -B scripts/learning.py preflight
python3 -B scripts/learning.py campaign --admission PREFLIGHT_DIRECTORY
python3 -B scripts/learning.py verify --run TRAINING_RUN_DIRECTORY
python3 -B scripts/learning.py summarize --admission PREFLIGHT_DIRECTORY
```

Setup downloads official hash-pinned binary wheels into unsynced tooling storage. It is
currently admitted only on macOS arm64 and does not install into system Python. A recorded
failed setup with all verified wheels retained can be recovered offline with
`learning_setup.py --resume SETUP_DIRECTORY`. Incomplete installation staging is disposable;
the failed setup records and unique learned artifacts remain retained.

Preflight compiles a release Rust evaluator, checks dense gradients, parameter export parity,
and bounded CPU throughput, then freezes its step-count decision and generated data. The
campaign runs the registered four arms and five seeds serially, verifying every completed
run before summarizing. Existing attempts, including failures, cannot be silently retried.
No warmup quality or held-out score selects architecture or hyperparameters. Stored raw
checkpoints and full evidence are local; ordinary Git contains source and compact identities.

`verify` re-executes the exported checkpoint in Rust and regenerates scoring from frozen
generator output. It checks source/build identity, every retained artifact, native/tensor
agreement, operation counts, and input/label boundaries. It does not independently repeat
optimization or attest historical timings. Current hosted checks exercise the stdlib
contracts and Rust fixtures; they do not install PyTorch or repeat research training.

EXP-0003 has a strict `noetloom.allocation.v1` contract and the same optional backend.
Read its [registered design](../../experiments/EXP-0003/design.md). Its parent inventory
requires the five retained EXP-0002 dense runs with their original artifact identities;
a fresh clone without these private local checkpoints cannot execute this follow-up.

```sh
python3 -B scripts/allocation.py preflight
python3 -B scripts/allocation.py campaign --admission PREFLIGHT_DIRECTORY
python3 -B scripts/allocation.py verify --run TRAINING_RUN_DIRECTORY
python3 -B scripts/allocation.py summarize --admission PREFLIGHT_DIRECTORY
```

The driver freezes parent weights, fits seven gate scalars per seed, and compares native
adaptive, top-one and dense execution on fresh held-out keys and structures. It preserves
the exact compiled executable inside preflight evidence, verifies every seed before summary,
and refuses duplicate attempts. Replay re-derives policy artifacts from the frozen parent
and selected gate. Analytical random-allocation accuracy is an expected control at equal
payload cost; it is not a measured third implementation or latency claim.

EXP-0004 has a strict `noetloom.representation.v1` contract. Read its
[registered design](../../experiments/EXP-0004/design.md) before execution. It uses the
already installed optional backend, starts every arm from its own initialization, and
does not inherit EXP-0002/0003 checkpoints or require another download.

```sh
python3 -B scripts/representation.py preflight
python3 -B scripts/representation.py campaign --admission PREFLIGHT_DIRECTORY
python3 -B scripts/representation.py verify --run TRAINING_RUN_DIRECTORY
python3 -B scripts/representation.py summarize --admission PREFLIGHT_DIRECTORY
```

The development preflight checks sampled gradients, native agreement and input boundaries,
then admits a common update count using throughput alone. The campaign fits four arms and
five seeds serially, retains all three validation checkpoints and the selected parameters,
and refuses replacement attempts. Rust replay verifies predictions, held-out transport
interventions, validation objectives, resource counts and persisted intermediate states.
The summary reports the registered retain/reject decision separately from execution success;
if every arm fails the task-acquisition floor, the representation comparison is inconclusive.
Replay requires the recorded source commit and intact local artifacts, including its preserved
executable. Hosted checks exercise contracts and native fixtures without repeating training.

These saved checkpoints contain weights and identity metadata, not the full Adam/RNG/data-order
state required for exact training continuation. Native `resume` reopens inference state;
the setup `--resume` option recovers dependency installation. Neither resumes model training.

## Acquisition calibration (EXP-0005)

The [registered development pilot](../../experiments/EXP-0005/design.md) implements N-007's
stages and fitting-evidence boundary. Existing experiment drivers retain their frozen contracts.

```sh
python3 -B scripts/calibration.py preflight
python3 -B scripts/calibration.py inject --admission PREFLIGHT_DIRECTORY
python3 -B scripts/calibration.py pilot --admission PREFLIGHT_DIRECTORY
python3 -B scripts/calibration.py verify --run TRAINING_RUN_DIRECTORY
python3 -B scripts/calibration.py summary
```

The pilot executes the declared short/long choices, keeps all three seeds per attempted
condition, stops each model at a failed stage, and replays completed fitting records in a
fresh process. `train` accepts `--arm`, `--stage`, `--condition` and `--seed` only within that
same contract. No command resets failed attempts. `confirm` additionally requires a separate
committed `experiments/EXP-0005/confirmation.json` selected after development; no such final
access is implied by the pilot. Fitting, verification and resource outcomes remain distinct.
An expected post-fit injection exits successfully only when those three outcomes are correct;
its run remains failed. All parameter artifacts support inference, not optimizer continuation.
`verify --development-transfer --run RUN` additionally requires the entire arm/condition to
pass its three-seed mixed-format gate. It consumes a replay allowance. The original pilot at
`734e3d6` performed three diagnostics too early; its result record preserves that deviation.
Historical replay requires its recorded source, available in the private evidence bundle.
`summary` verifies each recorded source against its exact Git revision and reports selections
separately by revision. Its confirmation decision requires successful fitting, verification,
resource admission and a matching completed replay for every frozen seed.
The [confirmation amendment](../../experiments/EXP-0005/confirmation-amendment.md)
freezes `shared_rows`, `mixed`, `long`, final-step selection and five fresh seeds. Execute
each with `confirm --admission PREFLIGHT_DIRECTORY --arm shared_rows --stage mixed
--condition long --seed SEED`, then `verify --run CONFIRMATION_RUN_DIRECTORY`.

The explicit `local-calibration` profile allows 50,000 presentations, 16 MiB output and
120 seconds per worker with the original cache/headroom limits. Whole-study ceilings also
apply, including failed attempts and replay. It does not replace `local-small` or `ci-smoke`.
Source and protocol must be committed before execution. CPU PyTorch remains optional and
uses the existing isolated tooling installation; hosted tests do not repeat learning.

`python3 -B scripts/artifact_backup.py pack --scope prior` prepares the historical bundle;
`--scope calibration` prepares new pilot artifacts. The tool creates no network transfer.
`restore --archive ARCHIVE --inventory INVENTORY` verifies the archive and all extracted
bytes in a fresh cache directory. Inference replay is a separate check. The owner's
[private destination and restore scope](../evidence/N-007-recovery.json) are recorded explicitly.

## Bootstrap commands

Use Python 3.11+ from the source checkout root. The CLI is `python3 -B -m noetloom`.
The `-B` flag keeps bytecode out of the working tree. No external Python package is required.

| Command | Effect and output |
| --- | --- |
| `status` | Read-only JSON view of the active or dependency-ready plan item and all statuses |
| `check` | Validate versioned contracts, plan dependency graph, references, Python syntax, and nonignored/tracked working-file budgets |
| `doctor [--cache PATH]` | Read-only host information and conservative admission check for the profile's maximum run output |
| `run PROTOCOL [--cache PATH]` | Validate and execute a supported harness protocol in a fresh directory outside the checkout |
| `verify-run DIRECTORY` | Check run bytes and exact runtime source, then regenerate all predictions and scores without writing files |

Without `--cache`, use `NOETLOOM_CACHE` or `~/.cache/noetloom`. `run` returns `directory`,
`run_id`, `status`, `bytes_written`, and prediction count as JSON. `verify-run` requires that
the directory retain the run ID as its basename. Its JSON includes `harness_verdict`,
`manifest_sha256`, `source_digest`, and the replayed prediction count.

`doctor`, `run`, and `verify-run` also accept `--profile local-small` (the default) or
`--profile ci-smoke`. Hosted CI selects the latter explicitly for disposable smoke runs.
There is no environment-triggered switch or automatic relaxation after an admission failure.

Exit 0 means the requested check passed; exit 1 means a complete harness result failed;
exit 2 means invalid input, failed storage admission, or an execution/verification error.
Error objects go to stderr. A verified negative run returns 1: integrity is not experiment success.
The CLI's `--help` provides argument syntax.

## Formats and implementation boundaries

| Format | Version | Owner |
| --- | --- | --- |
| Resource policy | `noetloom.resources.v1` | `config/resource-policy.json`, `validate_policy` |
| Active queue | `noetloom.plan.v1` | `docs/state/plan.json`, `validate_plan` |
| Sources | `noetloom.sources.v1` | `docs/research/sources.json`, `validate_sources` |
| Hypotheses | `noetloom.hypotheses.v2` | `docs/research/hypotheses.json`, `validate_hypotheses`; mechanism candidates and representation horizon questions |
| Harness protocol | `noetloom.experiment.v1` | `experiments/EXP-0001/protocol.json`, `validate_experiment` |
| Learned selection protocol | `noetloom.learning.v1` | `experiments/EXP-0002/protocol.json`, `validate_learning_protocol` |
| Read allocation protocol | `noetloom.allocation.v1` | `experiments/EXP-0003/protocol.json`, `validate_allocation_protocol` |
| Problem representation protocol | `noetloom.representation.v1` | `experiments/EXP-0004/protocol.json`, `validate_representation_protocol` |
| Runtime inventory | `noetloom.source.v1` | `source.json` in each run, `source_identity` |
| Run manifest | `noetloom.run.v1` | `manifest.json` in each run, `_manifest` |
| Harness report | `noetloom.harness_report.v1` | `report.json` in each run, `verify_run` |

Contract functions live in [contracts.py](../../noetloom/contracts.py); execution and replay
live in [runner.py](../../noetloom/runner.py). The runtime inventory hashes the Python files
directly under `noetloom/`. Protocol and policy snapshots are separately hashed payloads.
The Python execution API requires the supplied root to be the checkout actually imported.
It refuses on-disk runtime edits after import; start a fresh process from the intended
checkout after editing code. Replay checks the recorded source against that loaded inventory.
Python/platform observations are recorded; deterministic replay must match and can refuse
an environment whose behavior differs. The inventory is not a dependency lock for a future
training backend. Extend it deliberately if runtime code or dependencies move elsewhere.

`check` sees tracked files and nonignored untracked files. It rejects bulk learned array/model
formats even if force-added. It does not audit historical Git object sizes, validate every
Markdown anchor, fetch remote links, or certify scientific conclusions. Future formats need
versioned validators and behavior tests; do not add speculative generalized plugin machinery.

## Model input-validity audit

`python3 -B scripts/audit_calibration_inputs.py` reproduces the retrospective EXP-0005
counterexamples and partition counts using the standard library. It prints compact JSON
with source hashes, opposite-query checks, exact/latent/row-symmetry overlap and previously
published per-format scores. It accesses no checkpoints and performs no fitting or new
learned prediction. Historical confirmation cases are reconstructed for this audit; they
remain retired. Exit 0 means the audit executed, **not** that the model passed admission.

Add `--require-transfer` to enforce the reported input-validity gate. Exit 1 is expected
for EXP-0005's shared-row configuration because different required answers share consumed
inputs. Known-equivalent holdout overlap also prevents a new-computation transfer claim.
The [evaluation contract](../evaluation.md#check-what-the-learner-can-actually-observe) requires
future protocols to apply these checks to their own actual model paths before fitting.

## Learned transition pilot

EXP-0006 uses `python3 -B scripts/transitions.py preflight` after committing its reviewed
sources and [registration](../../experiments/EXP-0006/protocol.json). It requires the existing
optional PyTorch environment, `local-calibration` admission and the shared cache lease.
Preflight checks source-specific execution and throughput, not acquisition. Then use:

```sh
python3 -B scripts/transitions.py inject --admission /absolute/preflight-directory
python3 -B scripts/transitions.py train --admission /absolute/preflight-directory --arm shared_transition --stage tiny --condition lr003 --seed 9103
python3 -B scripts/transitions.py verify --run /absolute/fitted-directory
python3 -B scripts/transitions.py summary
```

Arms are `shared_transition` and `direct`; stages are `tiny`, `one`, `mixed`; conditions are
`lr003` and `lr010`. The protocol fixes three development seeds, advancement, duration,
checkpoint selection and aggregate budgets. Failed identities cannot be retried or hidden.
`verify --development-transfer` requires the arm's complete three-seed mixed acquisition;
ordinary fitting and replay do not access transfer outcomes. The driver has no final-evaluation
command: confirmation needs its own later registration. A successful fit can still fail its
acquisition gate; exit 0 means execution and verification completed. `inject` exits 0 only
when the deliberately failed verification preserves completed fitting and admitted resources.
Pass the resulting transfer-evaluation directory to ordinary `verify --run` to recompute
all its saved transfer and control predictions in another process. This also tests saved
native-state continuation through the longer rollouts.

`python3 -B scripts/artifact_backup.py pack --scope transitions` bundles every transition
attempt plus its committed sources under existing archive size limits. It performs no upload
or retirement. Follow the [storage contract](../storage.md) for private copying, inventory
verification and inference replay from restored bytes.

## Existing-transition development diagnostic

After committing the [EXP-0007-D1 registration](../../experiments/EXP-0007/diagnostics.json)
and implementation, `python3 -B scripts/transition_diagnostics.py run` audits the original
saved prefix predictions, evaluates the six preselected one-step/mixed snapshots and fits
one ordinary affine reference from allowed observations. It copies and validates exact input
bytes into the new run, leaving the historical campaign unchanged. There is no final-data
or neural-training operation.

`python3 -B scripts/transition_diagnostics.py verify --original /absolute/diagnostic-run`
recomputes the complete diagnostic in a fresh process, including the charged affine solve.
One run and three replays are the whole admitted attempt budget, including failures.
`python3 -B scripts/artifact_backup.py pack --scope transition-diagnostics` includes the
diagnostic attempts and their committed source. The optional `--input-root` on `run` selects
an intact restored historical artifact bundle; it does not bypass original hashes or source.

## Rust foundation

Use `python3 -B scripts/rust.py check` for formatting, all Rust test targets, and Clippy with
warnings denied. Use `python3 -B scripts/rust.py fixture` to build the example, run its scripted
state transition, and verify it in a second process. Exit 0 means success; exit 1 means a
build, admission, identity, or execution failure. Both commands accept `--profile ci-smoke`
only for explicitly disposable CI work; local default admission remains unchanged.

`NOETLOOM_TOOLING_CACHE` defaults to `~/.cache/noetloom-tooling`; its `cargo-target` and
`cargo-home` directories hold bounded build and dependency output. The driver sets two
compiler jobs and disables incremental compilation. `NOETLOOM_CACHE` selects the shared
run cache/lease. Builds and runtime jobs must not overlap. The Rust 1.98 toolchain is pinned
in `rust-toolchain.toml`; install that toolchain separately if absent.

The fixture emits `execution.json`, `restart.json`, `manifest.json`, and its immutable state
directory. A failure retains evidence and has no successful completion marker. The native
execution receipt is `noetloom.execution.v1`; the store index is `noetloom.state.v1`.
`noetloom.rust_build.v1` embeds a sorted path/SHA-256 inventory of Rust sources/tests/examples,
workspace/crate manifests, lockfile, and toolchain pin, plus compiler/target/profile/flags.
The driver checks it against current source and records the actual binary hash. This identity
is separate from `noetloom.source.v1`, which continues to identify only the Python harness.

Receipts distinguish activation payload I/O, commit validation I/O, metadata bytes,
logical active values, staged bytes, nominal scalar work, graph/trace bytes, and elapsed time.
They do not certify process memory, power, learned capability, or comparative efficiency.

## Optional ShardLoom infrastructure probe

`python3 -B scripts/shardloom_probe.py --binary /absolute/path/to/shardloom` generates 512
synthetic trace-shaped rows, runs three public SQL queries through Vortex preparation/native
execution, exports small JSONL results, and checks them against an independent reference.
`--source-checkout PATH` records source context but does not claim that commit built the binary.
The actual binary hash is recorded. The command does not install or build ShardLoom.

Output stays under the shared run cache and lease with 8 MiB/30-second limits. The engine
request is 1 GiB/two workers; any weaker enforcement reported by its envelope remains visible.
Exit 0 means all three scoped queries and route checks passed, 1 means partial/unsupported
coverage, and 2 means an admission or driver failure. Full envelopes, results, failures, and
the prepared Vortex file remain available; `report.json` records exact identities and limits.
This optional local probe is not required to build or test the independent Rust core.
