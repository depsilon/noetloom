# Project operation

The active agent reads the actual conversation and local files. The helper reads files
and runs declared checks. Neither receipts nor checkpoints are another work queue.

| Owner | Responsibility |
| --- | --- |
| Project | Purpose, requirements, authority, constraints, deferred scope |
| Architecture | Components, data ownership, decisions and tradeoffs |
| Plan | All active items in dependency/value order |
| Validation | Commands, input coverage, acceptance proof boundaries |
| Completed | Historical outcomes, evidence, and reopening events |
| Feedback receipts | What input was captured, applied, superseded, or acknowledged |
| Checkpoint | Current pause state and a concrete hint for continuation |

Paths come from `.noetloom/manifest.json`. Use local skills for intake, work, and
verification. The CLI prints JSON; exit 0 means the requested helper operation
succeeded, 1 means a check failed, and 2 means invalid input or a state error.

## Commands from the generated project root

```sh
python3 -B .noetloom/project.py status
python3 -B .noetloom/project.py check
python3 -B .noetloom/project.py feedback record --id message-2 --kind correction --message "Work offline; defer authentication."
```

The agent now updates the relevant owners and affected work. A previously completed
affected item first reopens with `reopen P-001 --feedback message-2 --reason "Offline requirement changed"`.
After applying the edits:

```sh
python3 -B .noetloom/project.py feedback apply --id message-2 --disposition accepted --summary "Offline storage required; authentication deferred." --roles project architecture plan validation --items P-001
```

The agent tells the user what changed. Only after delivering that response:

```sh
python3 -B .noetloom/project.py feedback ack --id message-2 --message "Offline storage is now required and authentication is deferred."
python3 -B .noetloom/project.py verify application
```

Inspect the results and use the returned check record ID:

```sh
python3 -B .noetloom/project.py complete P-001 --evidence check-RETURNED_ID --summary "Implemented and exercised the required behavior."
```

These IDs illustrate commands, not existing evidence. `--help` on each command shows
its full arguments. `feedback apply` supports accepted, merged, already-addressed,
deferred, rejected, and answered. `--supersedes` names earlier applied messages.
`feedback classify` assigns a concrete kind to pending unclassified capture.

`checkpoint --item P-001 --next "Add the reload regression test"` stores a resume hint;
omit the item after all work is complete. A pause/resume is a recorded receipt with
kind `pause` or `resume`, applied as accepted. Checkpoints cannot clear pause. Status
prioritizes interrupted writes, pending input, pause, and then ready work. It exposes
applied but unacknowledged feedback independently of work completion.

`recover` finishes an interrupted helper transaction after checking for intervening
edits. If a conflict exists, inspect the journal and preserve the user's edits before
deliberately resolving it; do not delete the journal as a generic repair. Manual
semantic edits are not transactional: leave the feedback pending until all affected
owners are reconciled. Another session will see and finish that pending input.

`adapters` regenerates thin Claude entries after canonical skill changes. `check`
detects adapter drift, invalid work dependencies, missing owners, cross-project
records, and stale completion evidence. It does not execute application tests.

## Verification records

The plan and validation Markdown owners contain marked JSON blocks. Edit their JSON
directly while preserving each marker and surrounding prose. The generated files
provide an initial example. Check commands are argument arrays, with `{python}` for
the helper's interpreter, project-relative `cwd`, explicit file-glob `inputs`, and
`timeout_seconds` in (0, 3600]. Required patterns must match files. Input contents and
the set of matched files are fingerprinted before and after each command.

Include all sources needed to justify the check; the helper cannot discover omitted
dependencies. Framework consistency and successful exits do not replace semantic
review. Stale evidence must be refreshed through reopening and new checks; historical
results remain historical. An unrelated item's checks stay valid when their declared
inputs and acceptance are unchanged.
