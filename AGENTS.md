# Working on Noetloom

Noetloom is a portable framework for autonomous software development. If asked to build
a project using it, read [BOOTSTRAP.md](BOOTSTRAP.md) and create/adopt the requested
workspace. Applications do not belong in this reference kit except maintained examples.

For changes to Noetloom itself, inspect Git changes and read [the objective](docs/project.md),
[the single plan](docs/plan.md), [design](docs/architecture.md), and the latest progress.
[The operating method](docs/operating-model.md) is authoritative and complete in plain
language. This repository opted into [optional helper records](docs/helpers.md):
`python3 -B .noetloom/project.py status` locates current work and unresolved input.
That choice does not make helpers mandatory for projects using the method.

| Work | Relevant local guidance |
| --- | --- |
| Derive a new project's phases and guide its build | .agents/skills/noetloom-bootstrap/SKILL.md |
| Reconcile consequential input, findings, or pause/resume | .agents/skills/noetloom-intake/SKILL.md |
| Implement, repair, replan, and continue | .agents/skills/noetloom-work/SKILL.md |
| Verify acceptance and finish delivery | .agents/skills/noetloom-verify/SKILL.md |

Read these files directly; native discovery is optional. Reconcile newer messages before
a checkpoint. Select concrete ready work, implement it, inspect behavior, test and repair,
update evidence, and continue across phases. Replan necessary missing work within the
objective. Keep decisions and reviews in the one plan; preserve reversals and deferred scope.
Capture, application, and a response delivered are distinct when that distinction matters.

Preserve existing permission grants and actual boundaries. Make routine reversible choices
without repeated approval. Stop at the agreed completion boundary, explicit pause, exhausted
host/resources, or a genuine blocker. Preserve unrelated user work, reference repositories,
licensing, and external artifacts. No helper or instruction grants new external authority.

The optional kit uses Python 3.11+ and the standard library. Keep generated projects
self-contained and canonical skills shared with thin host entries. Run the full small suite
and kit checks at completion: `python3 -B -m unittest discover -s tests -v` and
`python3 -B -m noetloom check`. [Validation](docs/validation.md) records meaningful proof.
Update the plan, [completion history](docs/completed.md), and checkpoint. Follow authorized
Git/CI delivery through completion; distinguish host execution from compatibility checks.
