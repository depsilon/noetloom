# Design and references

## Decision

The existing coding agent owns development: interpretation, phase synthesis, guidance,
implementation, verification, repair, integration, replanning, and acceptance. The
authoritative [operating method](operating-model.md) expresses that loop in ordinary
instructions. Project files preserve the objective, actual plan, contracts, evidence,
authority, and continuation state. They work with ordinary application tools; neither
a particular record format nor a Noetloom runtime is part of the baseline contract.

The readable templates are optional outlines. They do not synthesize phases. An agent
must inspect the actual workspace, map requested capabilities and risks, write concrete
work and checks, and review the plan against the objective. The ToolShelf exercise starts
with a brief and method only so the resulting plan and application are agent-derived.
Phase boundaries trigger verification and continued execution, not routine approval.

## Optional helper profile

The standard-library kit remains available for projects that choose machine-checked
local records. Bootstrap copies a standalone helper, the complete operating/helper
guides, and local skills into another workspace. Generated entrypoints name actual
owner paths directly. Existing applications can be adopted; destination conflicts
are checked before writes. Generated projects do not import the kit or private skills.

The manifest binds five document roles: project, architecture, plan, validation, and
completed. Roles can share Markdown files. Plan, validation, and completion each have
one marked JSON block so humans and agents can edit prose while the helper validates
the executable records. This is the selected plan representation, not an additional
queue. The initial P-000 planning sentinel is blocked and its placeholder check fails.
The agent must replace it with project-specific phases and meaningful checks before
execution. The helper does not claim to judge phase quality or generate a real plan.

Feedback is an append-only sequence of recorded, optionally classified, applied, and
acknowledged events. A stable ID makes delivery retries idempotent; repeated text with
a new ID can express a reversal. Owner hashes support detecting application, but the
agent must judge whether the edits actually satisfy the message. Source labels and
acknowledgements are attestations, not authenticated host transcript evidence.

Checks use argument arrays without shell interpolation. Evidence binds a project ID,
check definition, explicit input file fingerprints, exit status, and current work
specifications. Completion moves an item out of the plan into history. Reopening
increments its cycle and preserves earlier evidence. Unrelated item evidence is kept.
The agent owns dependency impact, test adequacy, and the completeness of input patterns.

Multi-file helper transitions use a write-ahead journal and atomic file replacement.
Recovery accepts only the recorded before/after contents; intervening edits stop it.
A local OS lock serializes helper writers and releases when a process exits. The
helper is not a database or a security boundary against a process that can edit the
project directly. Checks are trusted project commands; timeouts and bounded published
logs are not a compute or filesystem sandbox. Inspect commands before running an
untrusted adopted project. Bootstrap is an installation operation: conflicts are
preflighted and ordinary write errors restore touched files; an OS crash during initial
installation can require inspecting/removing only its partial generated files.

Canonical skills live under `.agents/skills`. Claude entries contain descriptions,
relative links, and canonical content hashes; `adapters` regenerates them and `check`
detects drift. They are compatibility instructions, not a second policy library.
`CLAUDE.md` imports `AGENTS.md`. No hooks are installed. Host limitations are recorded
in [hosts.md](hosts.md).

The portable plugin copies those same canonical skill bytes into `skills/` and uses
the same bootstrap modules, helper, and templates. An explicit allowlist excludes
Noetloom's own work state. Packaging is a distribution step, not an agent runtime.
Default framework content is Apache-2.0. Original copied starter material is isolated
under MIT-0 `templates/`; the generator carries framework notices in `.noetloom/licenses/`
without creating an application license. See [licensing.md](licensing.md).

## Alternatives and limits

The readable method depends on a capable agent to judge evidence and follow the loop.
Optional helpers can detect declared stale checks and incomplete record transitions;
they cannot judge semantic completeness. Keeping these capabilities optional lets
existing projects retain their ordinary documentation and tools. A custom runtime
would duplicate host responsibilities and is outside the requested scope. Neither
instructions nor helpers keep a stopped host running, grant authority, or guarantee
application correctness. One observed native-agent build does not establish a causal
improvement over other workflows or execution on every host.

## Primary workflow reference

The inspected ShardLoom revision is
[`42eb2a033b9bc07859a58e1f8edb9c3f1a242302`](https://github.com/depsilon/shardloom/commit/42eb2a033b9bc07859a58e1f8edb9c3f1a242302).
These exact public files were read, including relevant helper code. No ShardLoom
checks were executed and its checkout was not modified.

| Source at that revision | Relationship generalized here |
| --- | --- |
| [AGENTS.md](https://github.com/depsilon/shardloom/blob/42eb2a033b9bc07859a58e1f8edb9c3f1a242302/AGENTS.md) | Route by task boundary and choose coherent work units. |
| [Execution plan](https://github.com/depsilon/shardloom/blob/42eb2a033b9bc07859a58e1f8edb9c3f1a242302/docs/architecture/phased-execution-plan.md) | One ordered queue, intake classification, acceptance and verification, separate completed ledger. |
| [Architecture review](https://github.com/depsilon/shardloom/blob/42eb2a033b9bc07859a58e1f8edb9c3f1a242302/docs/architecture/global-architecture-review.md) | Findings become work only through explicit plan promotion; claims require evidence. |
| [Focused-check helper](https://github.com/depsilon/shardloom/blob/42eb2a033b9bc07859a58e1f8edb9c3f1a242302/scripts/run_focused_checks.py) | Run selected checks, stop on failure, record exact commands/results, retain broader completion gates. |
| [Documentation skill](https://github.com/depsilon/shardloom/blob/42eb2a033b9bc07859a58e1f8edb9c3f1a242302/docs/skills/documentation-rfc.md) | Scale documentation to the decision while retaining scope and verification. |
| [Developer-agent guidance](https://github.com/depsilon/shardloom/blob/42eb2a033b9bc07859a58e1f8edb9c3f1a242302/docs/skills/developer-agent-experience.md) and [contributing](https://github.com/depsilon/shardloom/blob/42eb2a033b9bc07859a58e1f8edb9c3f1a242302/CONTRIBUTING.md) | Connect instructions, implementation, review, and completion authority. |

These sources inform ownership, intake, coherent work, and verification. The public
skills here are original project guidance. Private local engineering and verification
skills were used during development but are neither published nor required by generated
projects. The shared logo's source and license are recorded in [assets](../assets/README.md).
