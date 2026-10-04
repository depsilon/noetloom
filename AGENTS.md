# Working on Noetloom

Noetloom is a reference and generation kit for existing coding agents. It does not
run a model, host an agent, or receive conversations in the background.

If the request is to **build a project using Noetloom**, read [BOOTSTRAP.md](BOOTSTRAP.md)
and work in the requested project workspace. Reading this repository does not put
the user's application here. `examples/` contains maintained demonstrations only.

For changes to **Noetloom itself**, inspect `git status --short --branch`, run
`python3 -B .noetloom/project.py status`, and read the role owners in its output.
[docs/plan.md](docs/plan.md) is the only active queue. Read relevant skills only:

| Situation | Canonical skill |
| --- | --- |
| New input, review findings, corrections, pause/resume | `.agents/skills/noetloom-intake/SKILL.md` |
| Implementation and continuation | `.agents/skills/noetloom-work/SKILL.md` |
| Verification and completion | `.agents/skills/noetloom-verify/SKILL.md` |
| Creating or adopting another project | `.agents/skills/noetloom-bootstrap/SKILL.md` |

Reconcile newer messages before following a checkpoint. Keep questions, suggestions,
requirements, and authorization distinct. A review is evidence to classify, not a
second queue. Preserve deferred scope on a plain continuation. Reopen affected
completed work without discarding unrelated completion evidence. Recorded, applied,
and acknowledged feedback are separate states; never claim a response was delivered
just because code or documents changed.

Use Python 3.11+ and the standard library for the kit. Keep generated projects
self-contained: no personal skill paths, private dependencies, model API, or service.
Keep one canonical skill source with generated Claude compatibility entries.
Keep instructions and documentation focused on the current project framework.
Preserve licensing, unrelated work, external artifacts, and source repositories used
as references. They are not dependencies or editing targets.

Implement a coherent authorized item through its checks and review. Continue while
the active host session and user authority permit. No helper grants permission to
publish, spend, deploy, or send messages. Existing explicit user authority persists;
do not ask repeatedly for routine actions within it.

Run `python3 -B -m unittest discover -s tests -v` and
`python3 -B -m noetloom check` at completion. Keep evidence compact and local. Update
the plan, historical completion record, and checkpoint before handing off. Report
actual host execution separately from compatibility-file checks.
