# Design and references

## Decision

The existing coding agent owns interpretation, implementation, review, and acceptance.
Noetloom provides original public guidance and a standard-library source-checkout kit.
Bootstrap copies a standalone helper and local skills into another workspace. Generated
projects do not import the kit or refer to personal skill paths. Existing applications
can be adopted; all destination conflicts are checked before writes.

The manifest binds five document roles: project, architecture, plan, validation, and
completed. Roles can share Markdown files. Plan, validation, and completion each have
one marked JSON block so humans and agents can edit prose while the helper validates
the executable records. This avoids a second hidden JSON backlog. The initial plan
requires real application implementation and its placeholder check deliberately fails.

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

A documentation-only template cannot detect stale checks or incomplete feedback
application. A custom agent runtime would duplicate host responsibilities and require
new operational infrastructure. The selected helper is limited to local records,
validation commands, adapters, and state transitions. It does not infer requirements,
approve changes, schedule work, or guarantee application correctness.

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
