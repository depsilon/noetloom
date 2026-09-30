# Research and agent operating model

## Authority and source ownership

| Question | Authoritative source |
| --- | --- |
| What is the system meant to become? | [Charter](charter.md) |
| What work is selected next? | [Plan](state/plan.json), exposed by `noetloom status` |
| What experiment may execute and within what limits? | Its registered protocol and [resource policy](../config/resource-policy.json) |
| What happened and which claim follows? | Run evidence, its verification, and a dated decision |
| What is permitted in this session? | The user's instructions and already granted authority |
| How should a task be performed? | [AGENTS.md](../AGENTS.md), relevant global skills, and the selected project skill |

On 2026-09-30, the user clarified that Noetloom should inherit the autonomy expected for
ShardLoom: they do not want to instruct the agent to push each completed change. For already
scoped Noetloom work, standing authority includes implementation, appropriate research,
verification, local commits, pushes of source/docs/tests/compact evidence to `depsilon/noetloom`,
and diagnosing, repairing, and pushing fixes until its CI checks complete successfully.
Use a pull request when it is part of the agreed repository workflow. Routine Git delivery
does not require a new permission question, including after compaction or in a later session.
The user's subsequent instruction to work through the queue autonomously also authorizes
continuing from a completed item into the next ready item, including the research and bounded
local implementation needed to make its protocol executable. Preserve the charter and record
each experiment's resource admission and decision before moving on.

This project-specific grant satisfies the global requirement for explicit push authority.
It is grounded in the user's instruction, not inferred from the roadmap. Preserve the
current work's scope and stop condition while carrying it through delivery. Other external
commitments, such as paid compute, bulk Release publication, redistribution of third-party
data, or merges outside a delegated PR workflow, still need their own applicable authority.
Finish reversible preparation before surfacing a genuine unresolved decision; do not invent
an approval gate for routine engineering or an already granted action.

## Select a coherent work unit

Run `python3 -B -m noetloom status`. It selects the active item, or the first planned item
whose dependencies are complete. The command proposes priority; it does not start work.
Only one primary item is active. Independent leaf assignments belong to that item.
The current request also controls the stopping boundary: a skill, documentation or planning
revision may select a future item without starting its learning campaign. Deliver that revision
and leave the future item planned. This does not revoke standing authority for routine execution
and delivery when the learning work is in scope.

Each queue item names its sources, outcome, acceptance conditions, verification, resource
profile, and stop condition. The bootstrap's future research items are design briefs:
their first task is to register an executable learning protocol. Where task acquisition is
unestablished, register a bounded development pilot before choosing the final comparison.
Permitted development choices may respond to pilot evidence within its declared search envelope;
record all attempts and costs. Freeze the confirmatory protocol after calibration and before
final evaluation. The harness runner
deliberately refuses training protocols until an appropriate learning contract exists.
Do not fill this gap with guessed commands or treat a broad acceptance list as preregistration.

Prefer one coherent implementation and evidence package over many tiny slices. Stop when
the item's stated boundary, including its delivery checks, is reached or a resource limit
is hit. Make evidence-supported research and engineering decisions within the agreed scope;
a routine design choice is not a reason to hand work back to the user. Update the plan and
decision before expanding scope. A negative result closes an experiment when its protocol
was sound; it need not close the research question. Inadequate acquisition is a calibration
outcome, not a verdict on all formulations of a broad architecture hypothesis.

## Continuity without an ever-growing prompt

At a handoff or context boundary preserve: the selected item, current user authorization,
working branch and changes, decisions already made, tests actually run, exact artifact
identities, unresolved evidence, and the next useful step. Resume that step. Do not replay
intake, reinterpret compaction as a new task, or repeat a permission request already settled.

Use concise queue evidence links and dated decisions. Long raw logs belong with runs, not
in the active plan. Completed items retain their evidence, but are not another current queue.
Split an unwieldy completed history into an archive only when it becomes a real loading cost;
do not manufacture ledgers before evidence exists.

## Primary and subagent responsibilities

The primary retains research judgment, experiment design, integration, and final acceptance.
Under the user's global routing policy, delegate bounded independent inventories,
source-field extraction, specified transformations, and already-selected checks to a suitable
economical leaf. Do not delegate uncertain research conclusions as mechanical work.

Every packet names exact inputs, exclusive writable paths or read-only scope, expected
output, acceptance checks, and stop conditions. A leaf gets no additional publication,
compute-spend, or messaging authority. Verify results against sources and executable checks;
confidence or a `COMPLETE` label is insufficient. Reuse useful worker context. Do not run
multiple local training or evaluation jobs merely because agents are available.

The current harness serializes writers within one cache root. Agents must share that root
for local runs. Different cache roots do not constitute a global scheduler or global quota.

## Evidence and completion

Close infrastructure work with executable checks and evidence. Close a research claim with
the [evaluation contract](evaluation.md), including controls and negative results. Record
which methods were actually read in the [source catalog](research/sources.json).

A decision states the observed result, supported scope, remaining uncertainty, next technical
choice, and artifact locations or content identities. `noetloom check` validates structure,
references, source syntax, and working-file budgets. It cannot establish scientific truth,
review quality, novelty, legal rights, or that a listed command was executed.

For published engineering work, retain the pushed commit and hosted check result. Local
verification is preparation for delivery; a push is followed by CI inspection and in-scope
repairs. See the [delivery skill](../.agents/skills/noetloom-delivery/SKILL.md). If an external
service or a genuine missing authorization prevents completion, record the concrete blocker
and completed preparation rather than asking the user to perform the routine steps.

The global [Noetloom grounding skill](skills/sl-dh-noetloom-repo-grounding/SKILL.md) is a
small project entrypoint. Repo-local research, evaluation, artifact, and delivery skills contain
task-specific guidance. General engineering and research standards stay in the user's
global skill library; ordinary contributors can use the repository without that library.
