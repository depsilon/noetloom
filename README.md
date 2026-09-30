# Noetloom

Noetloom is a research project for an original foundation architecture built around compact
learned computation, persistent mutable state, and selective use of computation. Language,
code, perception, and tool use are target capabilities. The architecture and its advantages
remain hypotheses.

The repository currently provides the research operating system and a small, reproducible
evaluation harness. It does not contain a trained model. Start with the
[charter](docs/charter.md) and [research program](docs/architecture/research-program.md).

## Run from a source checkout

Python 3.11+ and Git are sufficient. No package installation, model download, API key, or
network access is needed for the commands below. Run them from this repository's root:

```sh
python3 -B -m noetloom status
python3 -B -m noetloom check
python3 -B -m unittest discover -s tests -v
python3 -B -m noetloom doctor
python3 -B -m noetloom run experiments/EXP-0001/protocol.json
```

`run` prints the directory it created. Pass that directory to
`python3 -B -m noetloom verify-run` to check every artifact and replay every prediction.
Full command semantics and exit codes are in the [command reference](docs/reference/commands.md).

The first protocol checks mutable associative recall using four hand-written controls:
exact memory, absent memory, stale memory, and bounded memory. It probes retention,
revision, deletion, and capacity. A passing run establishes that this harness distinguishes
those controls; it establishes no learned intelligence or efficiency advantage.
The [first verified run](experiments/EXP-0001/evidence/2026-09-30/README.md) records the
results, exact artifact identities, review findings, and remaining proof gaps.

## Work autonomously with evidence

[AGENTS.md](AGENTS.md) is the agent entrypoint. The [operating model](docs/operating-model.md)
defines authority, continuity, subagent handoffs, and completion. The
[machine-readable plan](docs/state/plan.json) is the only active queue. Use `status` to select
the next item instead of reconstructing priorities from old discussions.

Research is organized by [falsifiable hypotheses](docs/research/hypotheses.json),
[reviewed source records](docs/research/sources.json), registered experiment protocols,
and dated [decisions](docs/decisions/0001-foundation.md). The
[evaluation contract](docs/evaluation.md) separates infrastructure checks from capability claims.

## Keep the working set small

Run output defaults to `~/.cache/noetloom`, outside the checkout. The default profile allows
a 10 GiB working cache and keeps 20 GiB of free disk headroom. EXP-0001 has an 8 MiB output
budget and a 30-second cooperative deadline. These are admission and output controls, not
an operating-system memory sandbox.

Git stores source, protocols, small evidence, and manifests. Bulk datasets and learned
checkpoints belong in versioned artifact storage; selected project assets can use GitHub
Releases when publication is authorized. See [storage and retention](docs/storage.md).
Ignoring a file does not prevent a synced folder from uploading it.

The bootstrap chooses no training backend and fixes no model size. The next learned
experiment must first measure an informative scale within the available hardware budget.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes. The repository is public;
no code license is granted by this bootstrap. Select an explicit license before inviting
reuse or distributing packaged code or learned artifacts.
