---
name: noetloom-verify
description: Verify and deliver work in a Noetloom-managed project using current acceptance evidence and an accurate account of limitations.
---

Read the selected item's acceptance and the validation owner. Define checks that
would fail for a plausible broken implementation. Use focused checks while editing,
then broader checks justified by the change. Do not equate generated files,
markers, or framework consistency with application behavior.

Each check has an ID, an argument-array command, project-relative cwd, explicit input
file patterns, and a timeout up to one hour. `{python}` selects this helper's interpreter.
No shell interpolation is performed. Include all relevant source, test, configuration,
fixture, and canonical skill files in `inputs`; a missing pattern is an error. Use
file globs such as `src/*.py`, not directories. The agent owns coverage selection.
Keep receipt, checkpoint, plan, completion, and evidence files out of inputs when their
routine updates would invalidate the check itself. Plan item specifications are bound
to evidence separately. Never omit actual application inputs merely to avoid staleness.

Run `python3 -B .noetloom/project.py verify CHECK_ID ...`. The helper records commands,
exit status, bounded published output, source fingerprints, and work specifications.
It rejects changed inputs during execution. Inspect results and exercise the real UI,
CLI, or API as appropriate. A passed command proves only what that command checks.
Review acceptance, failure paths, user intent, documentation accuracy, and residual risk.

Run `python3 -B .noetloom/project.py check` for framework consistency. Regenerate
Claude entries with `adapters` after canonical skill edits. Compatibility files are
not evidence that a different host executed a skill.

When acceptance is met, use `complete ITEM --evidence CHECK_RECORD_ID ... --summary
"OUTCOME AND LIMITS"`. This removes the item from active work and appends historical
evidence. It requires current passing results for every required check and the current
item specification. Changed acceptance or reopening requires new verification.
If later source changes make earlier evidence stale, investigate impact, reopen the
affected completed item with a recorded reason, and revalidate. Do not delete history.

Report the actual outcome, evidence, and remaining external limitations. Record delivered
acknowledgements separately through intake. Leave a checkpoint for remaining work.
