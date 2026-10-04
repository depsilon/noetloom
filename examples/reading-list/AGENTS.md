<!-- noetloom:instructions -->
# Working on reading-list

Use the readable [.noetloom/operating-model.md](.noetloom/operating-model.md) to drive
the objective through implementation, testing, repair, and integration. Inspect the
workspace and newer input, then read these local owners directly:

| Owner | File |
| --- | --- |
| Objective, constraints, authority, deferred scope | [Project](docs/project.md) |
| Design and project guidance | [Architecture](docs/architecture.md) |
| Single active phase plan | [Plan](docs/plan.md) |
| Checks and evidence | [Validation](docs/validation.md) |
| Completed history, created when needed | [Completion](docs/completed.md) |

| Work | Relevant local guidance |
| --- | --- |
| Consequential steering, review findings, pause/resume | [.agents/skills/noetloom-intake/SKILL.md](.agents/skills/noetloom-intake/SKILL.md) |
| Implementation and continuation | [.agents/skills/noetloom-work/SKILL.md](.agents/skills/noetloom-work/SKILL.md) |
| Testing, repair, acceptance, delivery | [.agents/skills/noetloom-verify/SKILL.md](.agents/skills/noetloom-verify/SKILL.md) |
| Project domain; resolve these questions into actual contracts | [.agents/skills/project-website/SKILL.md](.agents/skills/project-website/SKILL.md) |

Read these as ordinary files; native discovery is optional. Replace the planning
sentinel with concrete capability phases before implementation. Each phase needs an
outcome, dependencies, scope, instructions, guidance, acceptance, verification, and state.
Derive project-specific guidance and meaningful application checks; the starter outline
and deliberately failing check are not evidence of a working application.

Select ready work, implement it, test the actual user boundary, diagnose and repair
failures, update evidence and the plan, then continue the next phase. Replan necessary
missing work within the objective. Phase boundaries are not human approval gates.
Stop for completion, explicit pause, exhausted host/resources, or a genuine blocker.

Reconcile newer input before following a checkpoint. Preserve reversals and deferred
scope; reopen affected completed work. Use proportionate records and distinguish capture,
application, and a response actually delivered. Preserve unrelated work and permissions.
This project is self-contained and needs no private skills or Noetloom checkout.

This workspace opted into the Python helper profile. [.noetloom/helpers.md](.noetloom/helpers.md)
describes its commands and records. Its marked plan block is the single selected queue,
not an additional plan. Read owners directly to understand work; use helper status and
evidence operations for this profile. The application has its own tools and requirements.
No helper grants publication, deployment, spending, or messaging authority.
<!-- /noetloom:instructions -->
