---
name: noetloom-delivery
description: Deliver already scoped Noetloom changes through validation, commits, pushes, CI repair, and recorded completion using the project's standing Git authority.
---

# Noetloom delivery

Read the selected work item and the standing authority in the
[operating model](../../../docs/operating-model.md). The user expects routine commits,
pushes to `depsilon/noetloom`, and CI follow-through without a separate permission request
for each step. Preserve that grant across sessions. It applies to the current agreed work;
it is not permission to expand the research program or make unrelated external commitments.

## Deliver the coherent change

- Inspect the current checkout, branch, remote, and local changes. Preserve unrelated work.
  Use the existing suitable checkout; use `codex/` when a new branch is needed.
- Run the checks appropriate to the change. The bootstrap's normal completion checks are
  `python3 -B -m unittest discover -s tests -v` and `python3 -B -m noetloom check`.
  Changes to generation, scoring, execution, storage, or replay also need an admitted
  EXP-0001 run and `verify-run`. Documentation edits do not require model training.
- Check what will enter Git. Keep raw runs, datasets, checkpoints, credentials, and private
  discussion exports out of the push. Use the
  [artifact skill](../noetloom-artifacts/SKILL.md) for bulk retention or publication decisions.
- Commit the coherent source, documentation, and compact evidence, then push to the agreed
  Noetloom branch. The initial empty repository can receive its reviewed foundation on
  `main`; subsequent work follows the repository's branch/PR workflow. Never force-push
  over another contributor's work to avoid resolving a normal integration issue.
- If a PR is part of the agreed workflow, keep its description aligned with the final
  implementation and follow through within the delegated merge scope. Creating a PR or
  pushing a commit does not by itself finish the work.

## Own CI through completion

Inspect the hosted run for the exact pushed commit. The bootstrap workflow tests Python
3.11 on Linux and Python 3.13 on macOS, then runs and replays EXP-0001 using the explicit
`ci-smoke` profile. Local runs keep the `local-small` profile. Do not weaken a local
budget or remove a required check to make CI appear successful.

For a failed check, obtain its logs, identify the failing boundary, reproduce where useful,
repair related failures as one coherent change, and push the fix. Use the global debugging
and verification workflows as needed. Keep following the new commit until required checks
pass or a concrete external blocker remains; do not ask the user to push fixes manually.

Retain a run URL or comparable check identity with the pushed commit in compact evidence
when it closes a work item. Update the single plan and give a concise result, actual checks,
and remaining limitations. A context boundary or progress question does not revoke authority.
