---
name: noetloom-work
description: Implement or resume authorized work in a Noetloom-managed project from its single plan and durable checkpoint.
---

Read current instructions and inspect workspace changes. Run
`python3 -B .noetloom/project.py status`. Reconcile newer messages and pending feedback
with the intake skill first. Honor pause; a checkpoint is a resume hint, not authority.
Read the project owner for purpose, constraints, deferred scope, and permissions, then
the selected plan item and relevant domain skill. Do not load every skill or archive.

Work on a coherent outcome with explicit scope, acceptance, dependencies, and checks.
The plan's `items` block is the only queue; keep explanatory prose consistent with it.
Audits and design documents inform that queue, never compete with it. Small projects
can combine roles. Add a decision document only when a material tradeoff needs a
durable explanation; link it from its owning project/architecture document.

Implement the actual deliverable, test behavior at the user's boundary, and inspect
the result. When adopting an application, preserve its existing architecture and
instructions unless the requested change warrants a revision. If private guidance
helped, write only project-specific, independently understandable public requirements.

Use the verify skill before closure. Continue through authorized ready work in the
same active session; do not wait for repeated continue prompts. Pause for genuinely
missing input or authority, not for ordinary reversible implementation choices.
External actions still require their actual authorization. Noetloom supplies none.

Before interruption, run `checkpoint --item ITEM --next "CONCRETE NEXT ACTION"` with
the current item, or omit `--item` when no active work remains. Include unresolved
decisions and proof gaps in their owner documents. The checkpoint must not introduce
new scope. On resume, a changed plan or newer message takes precedence over the hint.
