---
name: noetloom-intake
description: In a Noetloom-managed project, reconcile new input or review findings with requirements, decisions, work, and verification.
---

Run `python3 -B .noetloom/project.py status` from the project root. Reconcile the
newest delivered input before trusting a checkpoint, including input not yet recorded.
Read the owners returned by status; do not reconstruct decisions from memory.

Capture material input with `feedback record --id MESSAGE_ID --kind KIND --message
"TEXT"`. Use a stable host message ID when available, otherwise a new local identifier.
Retry the same ID only for identical input. A later reversal gets a new ID. Use
`--source review:NAME` for review evidence; a receipt does not grant authority.
For ambiguous capture, use `unclassified`, then `feedback classify --id ID --kind KIND`.

Classify the message in context: question, suggestion, requirement, correction,
instruction, review, pause, or resume. A capability question is not implementation
authority. Split mixed input into related receipts if its parts need different
dispositions. Resolve short replies against the proposal they answer.

Choose accepted, merged, already-addressed, deferred, rejected, or answered. Explain
why. Reviews supply candidate findings; promote only justified, authorized changes
into the one plan. Record deferred scope and the condition for revisiting it in the
project or decision owner, not as a hidden backlog in a receipt or checkpoint.

For accepted changes, update the owning requirements, architecture/decisions, relevant
skills, plan, and checks as needed. Identify affected completed work and run
`reopen ITEM --feedback ID --reason "WHY"` before changing that item's acceptance.
Keep unrelated completion evidence. Reopening increments the item cycle so previous
test results cannot close revised work. Check dependencies, including completed
dependants that may also be affected; the helper cannot infer semantic impact.

After owner updates, use `feedback apply --id ID --disposition accepted --summary
"WHAT CHANGED AND WHY" --roles project plan validation --items ITEM`, listing only
actual affected owners/items. Use `--supersedes EARLIER_ID` for explicit reversals.
Nonchanging dispositions still need an explanation. A question or suggestion cannot
be applied as implementation; capture actual authorization separately if it arrives.

For an explicit pause/resume, record the corresponding kind and apply as accepted.
Pause stops implementation; resume clears pause but does not revive deferred scope.
Saving a checkpoint does not clear pause. A plain continue resumes the current
durable scope, after newer input is reconciled.

Tell the user what changed or answer their question. **After that response has been
delivered**, record `feedback ack --id ID --message "DELIVERED RESPONSE"`. Application
is not acknowledgement. On resume, deliver still-unanswered responses; if previous
delivery cannot be established, say so rather than marking it acknowledged by guess.

If capture was interrupted, status shows pending reconciliation before implementation.
If a helper write was interrupted, inspect its transaction and run `recover`; conflicts
with intervening edits stop recovery. Never discard a receipt to make status green.
