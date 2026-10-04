# Project starter material

Start from the objective and the [operating method](../docs/operating-model.md).
These outlines help express the resulting project; they are not finished requirements
or a prewritten implementation plan. All original material in this directory is MIT-0
under [LICENSE](LICENSE). Independent application code keeps its own licensing policy.

## Readable baseline

Use only the roles the project needs, combine files when useful, and replace prompts
with actual project decisions:

- [AGENTS.md](readable/AGENTS.md): local entrypoint, work routing, autonomous execution.
- [project.md](readable/project.md): objective, requirements, design, authority, deferrals.
- [plan.md](readable/plan.md): the phase-writing contract and one authoritative sequence.
- [guidance.md](readable/guidance.md): relevant recurring implementation rules.
- [validation.md](readable/validation.md): real checks and completion evidence.
- [progress.md](readable/progress.md): useful continuation state and consequential steering.

These are ordinary Markdown files. No parser, special marker, JSON block, command,
skill directory, or native file-discovery mechanism is needed to follow them.
Point the next agent or person to the actual entrypoint and named owners explicitly.

## Domain questions

Read a guide as ordinary text when its boundary is relevant, then specialize its rules
and checks to the application. Its SKILL.md wrapper is an optional discovery convenience.

| Boundary | Guidance to adapt |
| --- | --- |
| CLI or focused utility | [Input, output, error and deterministic behavior](domains/utility/SKILL.md) |
| Data workflow | [Schema, grain, provenance, reconciliation and safe writes](domains/data/SKILL.md) |
| Browser interface | [User flows, accessibility, responsive and storage behavior](domains/website/SKILL.md) |
| Deployment | [Target, authority, health, rehearsal and recovery](domains/deployment/SKILL.md) |

## Optional helper profile

The existing `base/` resources support the [Python helper profile](../docs/helpers.md).
Invoking that bootstrap chooses structured helper records and compatibility entries.
Its blocked planning sentinel requires the agent to derive real phases before work;
the helper does not turn a prompt into a plan. This profile is not required by the
readable baseline.
