# Bootstrap command reference

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
| Hypotheses | `noetloom.hypotheses.v1` | `docs/research/hypotheses.json`, `validate_hypotheses` |
| Harness protocol | `noetloom.experiment.v1` | `experiments/EXP-0001/protocol.json`, `validate_experiment` |
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
