# Autonomous development

Noetloom is a portable operating method for autonomous software development by a
capable coding agent. Given an objective, an actual workspace, and a completion
boundary, the agent derives the work and drives implementation, verification, repair,
and integration. The user owns the objective and major direction; the agent owns
routine development execution. Project generation initializes this process; later
messages steer it.

This document is the authoritative method. Reading and editing ordinary project files
and using the application's normal tools is sufficient. Any capable agent or human
can read it explicitly. No Noetloom command, JSON record, native skill discovery,
host adapter, or plugin installation is required. Optional automation is described in
[helpers.md](helpers.md).

## 1. Establish the objective and working boundary

Read the actual request, any supplied brief, newer messages, applicable instructions,
and the real workspace. Inspect existing code, tests, dependencies, Git changes, and
working behavior before choosing a design. Preserve unrelated work and existing policy.
For adoption, understand the existing architecture and a representative user flow first.
Create the requested application in its own workspace, not inside the reference kit.

Write a concise project owner that another developer could use without the conversation:

- The user, problem, intended deliverable, and observable success conditions.
- Required behavior, interfaces, data ownership, failure behavior, constraints, and
  explicit exclusions or deferred scope.
- The agreed completion boundary: for example, a locally working application with
  tests and usage documentation, or an integrated change with passing authorized CI.
- Existing authority for local changes, commits, remote writes, deployment, spending,
  and communication; identify which actions need additional permission.
- Material assumptions and unresolved questions, with their consequences.

Resolve routine reversible choices using evidence and sound engineering judgment.
Ask only when missing information materially changes the outcome, an irreversible
decision lacks authority, or a real blocker prevents progress. Continue independent
authorized work while awaiting an answer. An unanswered question is not approval.

## 2. Derive the implementation sequence

Turn the objective into concrete user journeys and system obligations. Trace each
required result to the inputs, state, interfaces, failure paths, and dependencies that
make it possible. Identify the earliest useful end-to-end behavior and the uncertainty
most likely to invalidate the design. Put an executable slice or bounded investigation
there, rather than building all layers before any behavior can be exercised.

Group related work into the largest coherent phases that can be implemented and
verified together. Order dependencies first, then user value and risk. Testing and
repair belong inside every phase. Final integration closes gaps across phases; it
does not postpone all verification until the end. A small change may need one phase;
a multi-capability project needs a real sequence, not an arbitrary phase quota.

Every phase in the single authoritative plan must state:

| Field | What the next developer needs |
| --- | --- |
| Outcome | The specific user or system capability made possible, not a list of files. |
| Entry and dependencies | What must already work; distinguish ready work from blocked work. |
| Scope and exclusions | The behavior and components this phase changes, and what stays deferred. |
| Work instructions | Concrete implementation steps, important contracts, and likely failure cases. |
| Relevant guidance | Local guidance or skills to read for this work, with a reason and actual path. |
| Acceptance | Observable conditions that distinguish complete behavior from a plausible stub. |
| Verification | Actual commands, scenarios, expected results, and evidence to retain. |
| State and exit | Current status, remaining issues, and evidence supporting completion. |

"Implement the project" is not an implementation plan. "Scaffold, implement, test" also
fails to identify capabilities, dependencies, or proof. For example, a document search
tool might first index a local corpus with stable document identities, then rank and
display useful matches, then integrate incremental updates and recovery. Each phase
would include representative queries, error cases, and checks against known documents.
These illustrate deriving a sequence, not mandatory phases to copy into other projects.

Before starting, challenge the plan: does every required outcome have an owner and
check? Can the first phase produce meaningful evidence? Are migration, recovery,
integration, usability, and delivery obligations covered where they actually matter?
Remove ceremony and speculative scope. Rewrite generic template text into the actual
project's instructions. Do not treat copying an outline as having planned the work.

## 3. Write and route relevant project guidance

Derive guidance from the project's risks and decisions. A data import may need key,
null, duplicate, provenance, and atomicity rules; a website may need keyboard, storage,
offline, and responsive behavior; deployment needs target, authority, health, and
rollback boundaries. Use relevant domain references as questions, then resolve them
for this project. Do not copy every domain's checklist.

Write independently understandable local guidance for recurring or consequential work.
Each guide should identify when it applies, the actual component/data contracts,
implementation rules, failure handling, checks, and the evidence needed to finish.
A short section in the project owner is enough when a separate skill would add no value.
Native SKILL.md packaging is optional; ordinary Markdown guidance is equally usable.

The project entrypoint maps each work boundary to its relevant local file or section.
Link that guidance from the phase that uses it. Read only the material needed for the
selected work. Never depend on a private global skill path or implicit host discovery.
If private expertise helped, express the resulting project requirements in original
local instructions; do not copy private content into a public project.

## 4. Execute the operating loop

While the active host and existing authority permit, repeat:

1. Reconcile new input and current workspace changes with the objective and plan.
2. Select the highest-value ready phase or coherent part of it. Satisfy dependencies;
   if one branch is blocked, continue useful independent work within the objective.
3. Read its relevant guidance, implement real behavior, and integrate it with the
   existing application. Keep source, configuration, tests, and usage instructions aligned.
4. Run focused checks and exercise the actual user boundary. Inspect outputs, files,
   UI behavior, or API responses; generated folders and passing marker checks are not proof.
5. Diagnose failures from logs, reproduction, and source. Fix the cause, add an appropriate
   regression check, and rerun affected verification. An ordinary failing test or build
   error is development work, not a reason to hand the task back.
6. Review acceptance, integration, error paths, and maintainability. Broaden validation
   when shared contracts or new concerns justify it. Fix actionable review findings.
7. Update the plan, material decisions, and evidence. Mark only demonstrated outcomes
   complete; retain exact unresolved work. Compare progress with the overall objective.
8. Select the next ready work and continue. Finishing a phase is an execution transition,
   not a mandatory approval gate or a request for another "continue."

Use concise progress updates to explain meaningful findings and decisions. Do not turn
every test, minor edit, or user clarification into a separate administrative record.
Delegate independent bounded work when the host and project permit, with explicit
ownership and verification; the primary agent remains responsible for integration.

## 5. Replan from evidence

The initial plan is a hypothesis about the work needed. If implementation reveals a
missing necessary capability, unsafe assumption, integration dependency, or inadequate
test, investigate it and revise the plan within the delegated objective. Do not stop
merely because the original checklist omitted it. An empty queue does not establish
completion when requested functionality is missing.

Record the evidence, why the change is necessary, affected phases and acceptance,
and the revised next step. Merge related work instead of creating competing audit or
repair backlogs. Reopen affected completed work and examine its dependants; preserve
unrelated results. A revised requirement or changed source can invalidate old evidence.
Historical evidence remains a record of what was checked at that time.

Prefer the smallest complete correction. Optional improvements and newly imagined
products are not necessary work. Record out-of-scope ideas as deferred with a condition
for reconsideration. Material objective changes, new external effects, or new costs
still need their actual authority; a plan entry cannot grant it.

## 6. Assimilate steering without making intake the product

Interpret new messages in context. A question calls for an answer; a suggestion is a
candidate; a requirement, correction, or explicit instruction can change authorized
work. Resolve short replies against the proposal they answer. Reviews provide evidence
to assess, not automatic scope. Choose accepted, merged, already addressed, deferred,
rejected, or answered, and preserve the reason when it matters.

For consequential changes, update the owning requirements, decisions, guidance, phases,
and verification before resuming affected work. Record explicit reversals and the earlier
decision they supersede. Preserve deferred scope on a plain continuation. Reopen only
affected completed outcomes, including dependants whose assumptions changed.

Use a short progress note or a small table to distinguish **captured**, **applied**, and
**answered to the user** when interruption could lose the distinction. For example:
"Offline correction captured; storage phase and persistence checks still need updating;
response not yet delivered." Update this note after reconciliation and after the actual
response. Do not claim acknowledgement merely because files changed. Routine questions
that do not affect durable scope need no separate receipt file or command.

An explicit pause stops implementation. Save useful state and wait for resumption.
A resume continues the current durable objective after newer input is reconciled;
it does not restore superseded instructions or revive deferred features.

## 7. Keep enough state for another session

The project entrypoint names the actual owners below. These are roles, not required
filenames or a mandatory directory count. Combine them when that makes the project easier
to understand. Keep one active plan; decisions, reviews, receipts, and checkpoints do
not become separate queues.

| Owner | Durable content |
| --- | --- |
| Project | Objective, acceptance boundary, constraints, authority, deferred scope. |
| Design and guidance | Actual components, data contracts, decisions, and work routing. |
| Plan | Ordered project-specific phases, status, dependencies, remaining work. |
| Validation and completion | Commands/scenarios, results, source revision or inputs, limits, completed outcomes. |
| Progress and continuation | Current phase, unresolved input, pause state, changed assumptions, concrete next action. |

Before interruption, leave a short continuation note with what works, what failed,
which checks were run, local changes to preserve, outstanding responses, and the next
action. A checkpoint is a hint, not authority or a substitute for the plan.

On arrival, a fresh session reads the entrypoint, project owner, current plan, and latest
progress. Inspect the actual workspace and reconcile pending input before trusting the
old next action. Select the relevant guidance, establish what evidence is still current,
and resume the loop without requiring the original conversation or global skills.

## 8. Close the agreed boundary

Stop when the objective's agreed completion boundary is met, the user pauses, usable
resources or host execution are exhausted, or a genuine blocker prevents useful work.
Do not stop for routine engineering choices or ordinary repair work. If blocked,
explain the concrete missing input or authority, preserve the next action, and state
what independent work was completed. Do not manufacture authority or unrelated tasks
just to keep running. Instruction files cannot keep an exited host alive.

Before declaring completion, compare the actual application with the original objective
and all accepted changes. Exercise a representative full user journey and relevant
failure paths; check integration and project instructions from a fresh reader's view.
When authorized delivery includes Git/CI, follow it through checks and repair, rather
than treating a push as completion. Deployment remains separate unless authorized.

Report the implemented result, exact meaningful verification, known limits, and any
remaining external boundary. Preserve completion evidence with its source revision or
input identity. Documenting a procedure, checking an adapter, or building a plugin does
not prove autonomous development, cross-host execution, or application correctness.
