# Noetloom

Noetloom is an experimental post-LLM foundation architecture intended to learn continuously,
reason with variable computation, and operate across multiple native representations.
The system itself is the proposed intelligence: compact learned machinery acting over
persistent, mutable, selectively activated state. Language, code, perception, and tool use
are capabilities it must learn. Neither an LLM nor a Transformer is a required foundation.
The architecture and its advantages remain hypotheses.

The repository provides a Rust core for persistent native state and bounded dynamic execution,
plus a Python research control plane and reproducible evaluation harness. Experimental trained
checkpoints remain in local artifact storage; weights are not included in this repository. Start with the
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

The Rust core adds revision-checked persistent cells, selective payload reads, shared numerical
operators, transaction-local writes, and controller-proposed work graphs. Its
[execution-provider boundary](docs/architecture/execution-providers.md) keeps physical storage
and computation replaceable. Its foundation controllers and weights are explicitly scripted fixtures.
With the pinned Rust 1.98 toolchain available, run:

```sh
python3 -B scripts/rust.py check
python3 -B scripts/rust.py fixture
```

The driver keeps builds and dependencies under `~/.cache/noetloom-tooling`, serializes runs,
and verifies committed state in a separate process. Fixture receipts include source/build,
provider, operator, snapshot, and resource identities. See the
[foundation design](docs/architecture/foundation-runtime.md) for scope and limits.

## Work autonomously with evidence

[AGENTS.md](AGENTS.md) is the agent entrypoint. The [operating model](docs/operating-model.md)
defines authority, continuity, subagent handoffs, and completion. The
[machine-readable plan](docs/state/plan.json) is the only active queue. Use `status` to select
the next item instead of reconstructing priorities from old discussions.

Routine commits, pushes, and CI follow-through for agreed Noetloom work are delegated.
The [delivery skill](.agents/skills/noetloom-delivery/SKILL.md) carries a coherent change
through hosted verification without requiring the user to direct each Git step.

Research is organized by [falsifiable hypotheses](docs/research/hypotheses.json),
[reviewed source records](docs/research/sources.json), registered experiment protocols,
and dated [decisions](docs/decisions/0001-foundation.md). The
[evaluation contract](docs/evaluation.md) separates infrastructure checks from capability claims.
The hypothesis registry also preserves foundational representation questions beyond the first
memory experiments. ShardLoom can earn a role in evidence analytics or physical execution;
it is not a required cognitive substrate.

## Keep the working set small

Run output defaults to `~/.cache/noetloom`, outside the checkout. The default profile allows
a 10 GiB working cache and keeps 20 GiB of free disk headroom. EXP-0001 has an 8 MiB output
budget and a 30-second cooperative deadline. These are admission and output controls, not
an operating-system memory sandbox.

Git stores source, protocols, small evidence, and manifests. Bulk datasets and learned
checkpoints belong in versioned artifact storage; selected project assets can use GitHub
Releases when publication is authorized. See [storage and retention](docs/storage.md).
Ignoring a file does not prevent a synced folder from uploading it.

The registered [EXP-0002 probe](experiments/EXP-0002/design.md) tests learned cell selection
against dense-read, frozen-routing, and no-history controls. Its optional PyTorch development
backend trains 359 initialized scalars; exported parameters execute in Rust. A bounded
preflight selects between two registered training budgets before fitting. This is a limited
mechanism experiment, not Noetloom's final architecture. See the
[learning commands](docs/reference/commands.md#registered-learning-probe).

The [first learned result](docs/decisions/0004-learned-selection.md) rejected that configuration:
selective reads averaged 72.6% accuracy versus 84.9% for the matched dense control, with one
near-chance training seed. Payload reads fell to 7.1% of dense, without a demonstrated
speed advantage. All five seeds and the full verification evidence are retained.

[EXP-0003](experiments/EXP-0003/design.md) tests a seven-scalar learned gate over the five
frozen dense readers. It must preserve quality and beat an input-independent allocation
control at equal payload cost, on fresh keys and operation structures. This is a registered
component probe; procedural reuse and a complete foundation architecture remain unproven.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes. Noetloom source and
documentation are available under [Apache-2.0](LICENSE). Datasets, separately distributed
weights, branding, and patent strategy have [explicit separate boundaries](docs/licensing.md).
