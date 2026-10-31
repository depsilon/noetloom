---
name: noetloom-continuity
description: Preserve and recover an active task through context compaction or session handoff, then continue authorized work from current local evidence.
---

Compaction continues the same task. Preserve its objective and valid authority, but
reconcile newer user messages before following an older next step. A question needs
an answer even if earlier work finished; a short reply belongs to the question or
proposal it answers. Reading an attachment or capturing a request does not answer it.

## Keep one useful continuation note

Update the project's existing progress/checkpoint at meaningful boundaries and before
a known context limit or handoff. Do not wait until the entire task is finished. Keep
the note concise, current and sufficient for the next decision:

- The active objective, latest unresolved steering, completion boundary, existing
  authority, explicit pause and deferred scope.
- The exact workspace or worktree, branch/revision when available, and owner paths.
- What works, what changed, unrelated edits to preserve, failed checks, and current
  validation evidence with its source identity. Distinguish completed actions from
  responses actually delivered to the user.
- Task-owned jobs and workers: identifiers, state, exclusive file ownership, unfinished
  outputs, artifact paths and any observation still needed before reuse or reassignment.
- The concrete next action, material unresolved decisions, and any successful recovery
  route or failed retrieval path the next session should avoid repeating.

Keep work selection in the existing plan; the note is a resume aid, not another queue.
Use a durable task-owned location appropriate to the host. Do not put credentials,
unrelated conversation, private operational details or raw tool dumps in public project
files. Private host/session pointers can stay in a separate task-owned continuation
note, referenced by the host when it supports one.

## Recover only what is missing

Read the supplied continuation summary or saved note first. Reconcile the latest user
messages, verify the exact checkout and its current changes, then consult the relevant
owners. Inspect known jobs and worker state through available host controls before
restarting a command or assigning their files. A missing worker connection does not
establish that its writes stopped. Continue independent work while resolving ownership.

Use history only to fill a specific missing requirement, response or authorization.
Start with one recent turn or the smallest supported page, omit tool outputs when the
interface permits, and extract only the needed material. Use actual thread identifiers
and returned cursors. Do not invent a host API or treat a context identifier as a chat ID.
Reuse a successful bounded result instead of repeatedly fetching it.

After a size-limit error, make at most one genuinely smaller request if available.
If that also fails, or the backend is unavailable, switch to the known checkpoint,
current diff, relevant commits and local owners. Repeated equivalent reads do not make
progress. File state can prove implementation; it cannot supply missing user permission.
Ask only when a material requirement or authority remains unrecoverable. Elapsed time
and a failed tool are not approval.

## Continue the work

Resume once the current objective, authority, workspace, completed work and next action
are established. Reuse checks whose source and execution assumptions remain valid;
rerun affected checks when changes or uncertainty justify it. Do not restart intake,
repeat opening plans or skill announcements, replay completed work, or require another
"continue" solely because the context changed. Report new findings or blockers instead.

Before finalizing, address the latest unresolved request, account for dispatched work,
and separate work completed from a response already delivered. An explicit pause still
stops execution. This guidance uses the active host's continuation facilities; it cannot
force compaction, resurrect an exited session, recover undelivered messages or start
background execution.
