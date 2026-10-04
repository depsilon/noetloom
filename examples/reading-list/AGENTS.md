<!-- noetloom:instructions -->
# Working on reading-list

Read applicable instructions and inspect workspace changes. Run
`python3 -B .noetloom/project.py status`, then read its project owner and selected
plan item. The manifest binds document roles; file count and paths may vary.

| Boundary | Local skill |
| --- | --- |
| New messages, findings, corrections, pause/resume | `.agents/skills/noetloom-intake/SKILL.md` |
| Implementation and continuation | `.agents/skills/noetloom-work/SKILL.md` |
| Verification and completion | `.agents/skills/noetloom-verify/SKILL.md` |
| Project domain | `.agents/skills/project-website/SKILL.md` |

Newest user input takes precedence over a checkpoint. Capture, apply, and acknowledge
material feedback separately. Suggestions and questions do not automatically authorize
work. Preserve supersession and deferred scope; reopen only affected completed work.
The plan owns all active work. Checkpoints and receipts explain state without becoming
queues. Continue authorized ready work while the host session is active.

Implement and exercise the actual application. Replace the bootstrap's deliberately
failing application check with meaningful tests and complete only with current evidence.
Generated structure alone is not completion. Preserve unrelated files and user work.
This project is self-contained; no private skills or Noetloom checkout is required.
Run `python3 -B .noetloom/project.py check` for its framework check. Use the copied
helper for all project operations; this workspace does not install the `noetloom` module.
No helper grants publication, deployment, spending, or messaging authority.
<!-- /noetloom:instructions -->
