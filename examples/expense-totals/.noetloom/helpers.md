# Optional helper reference

The readable [operating model](operating-model.md) is the complete autonomous development method. Python 3.11+ helpers are optional. Running `python3 -B -m noetloom bootstrap TARGET --name NAME --prompt REQUEST --domain ...` opts a project into this helper profile; it is not part of the baseline method. The profile uses the marked JSON block in its selected plan as the machine-readable representation of that plan. Do not create another active queue alongside it.

Bootstrap emits a blocked `P-000` item titled **Derive the implementation phases**. It is a sentinel, not an implementation plan. Before implementation, the agent must replace it with project-specific ready phases and checks that follow the operating model. Helpers cannot synthesize those phases, judge whether they are adequate, or grant permission. The copied `.noetloom/operating-model.md` and `.noetloom/helpers.md` remain readable reference documents in generated projects.

## Bootstrap and project root commands

Run bootstrap from the Noetloom checkout (or its installed command environment):

```sh
python3 -B -m noetloom bootstrap TARGET --name NAME --prompt REQUEST --domain utility
```

Domains are `utility`, `website`, `data`, and `deployment`. `--adopt` permits installing into a nonempty target after inspecting its existing code and instructions; bootstrap preserves existing application content and appends the managed Noetloom instructions. Existing conflicting framework paths cause an error and must be reconciled deliberately. Repeating an identical bootstrap request for an existing healthy project reports it as existing without changing files; a different request must be reconciled as new feedback in that project.

`--docs-dir PATH` selects the project documentation directory (default `docs`). It must be a safe project-relative document directory, outside `.noetloom`, `.agents`, `.claude`, and `.git`. `--compact` combines the architecture owner with the project owner and the completed-history owner with the plan owner. These options change the selected owners, not the single-plan rule. Bootstrap does not implement the application.

From the generated project root, the standalone helper accepts:

```sh
python3 -B .noetloom/project.py status
python3 -B .noetloom/project.py check
python3 -B .noetloom/project.py feedback record --id message-2 --kind correction --message "Work offline; defer authentication."
```

The helper prints JSON. Exit status 0 means the requested helper operation succeeded, 1 means a check failed, and 2 means invalid input or a state error. `--help` on each command gives the full arguments. The helper reads files and runs declared checks; it does not run an agent or implement work.

## Feedback, work, and recovery

The agent classifies feedback and reconciles affected owners and work. A completed item affected by a correction must first be reopened, for example:

```sh
python3 -B .noetloom/project.py reopen P-001 --feedback message-2 --reason "Offline requirement changed"
```

After making the changes, record how the feedback was handled:

```sh
python3 -B .noetloom/project.py feedback apply --id message-2 --disposition accepted --summary "Offline storage required; authentication deferred." --roles project architecture plan validation --items P-001
```

Supported dispositions are `accepted`, `merged`, `already-addressed`, `deferred`, `rejected`, and `answered`. `--supersedes` identifies earlier applied messages. `feedback classify` assigns a concrete kind to pending unclassified capture. The agent tells the user what changed; only after delivering that response should the receipt be acknowledged:

```sh
python3 -B .noetloom/project.py feedback ack --id message-2 --message "Offline storage is now required and authentication is deferred."
python3 -B .noetloom/project.py verify application
python3 -B .noetloom/project.py complete P-001 --evidence check-RETURNED_ID --summary "Implemented and exercised the required behavior."
```

Use the check record ID returned by verification as evidence. The example IDs are illustrative, not existing records. A `checkpoint --item P-001 --next "Add the reload regression check"` records a resume hint; omit `--item` when no active work remains. Pause and resume are feedback receipts of kind `pause` or `resume`, applied as accepted. A checkpoint cannot clear a pause. Status prioritizes interrupted writes, pending input, pause, then ready work, and reports applied but unacknowledged feedback independently of work completion.

`recover` finishes an interrupted helper transaction only after checking for intervening edits. If there is a conflict, inspect the journal and preserve the user's edits before deliberately resolving it; do not delete a journal as a generic repair. Manual semantic edits are not transactional. Keep feedback pending until all affected owners are reconciled; another session can see and finish that pending input. `adapters` regenerates thin Claude entries after canonical skill changes. `check` detects adapter drift, invalid dependencies, missing owners, cross-project records, and stale completion evidence; it does not execute application tests.

## Plan and validation JSON

The plan and validation Markdown owners contain marked JSON blocks. Edit the JSON directly while preserving its marker and surrounding prose. The plan block is the one selected plan's machine-readable representation, not a separate queue. Bootstrap's `P-000` sentinel must be replaced by reviewed, project-specific phases before work starts.

Check commands are argument arrays. `{python}` refers to the helper interpreter; `cwd` is project-relative; `inputs` are explicit project-relative file globs; and `timeout_seconds` must be in `(0, 3600]`. Each required input pattern must match at least one file. Include every source needed to justify a check because the helper cannot discover omitted dependencies. Before and after each command, the helper fingerprints input contents and the set of matched files. Successful exits and framework consistency do not replace semantic review.

Evidence is tied to the declared inputs and check definition. Changes to an item's acceptance, sources, or check definition make its evidence stale; reopen affected completed work and run fresh checks. Historical results remain historical. An unrelated item's checks remain valid when its declared inputs and acceptance are unchanged.

## Included material and licensing

Generated projects carry notices for included helper and starter materials. The helper,
copied operating/helper guides, and lifecycle skills are Apache-2.0; preserve applicable
notices and mark modifications when redistributing them. Original starter text in
`AGENTS.md`, `CLAUDE.md`, initial working documents, domain skills, generated Claude
entries, and `.noetloom/templates/` comes from MIT-0 `templates/` and can be adapted
without attribution. Generated records do not assign a license or copyright owner to
the application. Preserve existing instructions' and third-party terms. In a generated
project, see `.noetloom/licenses/README.md`; in the distribution, see `docs/licensing.md`.
