# Decision 0002: routine Git delivery is delegated

Date: 2026-09-30. Status: adopted.

The user clarified that Noetloom should receive the same autonomous execution style expected
for ShardLoom and that they do not want to instruct the agent to push each change. The
foundation's previous "no standing push grant" statement no longer describes the authority.

Record the grant once in the [operating model](../operating-model.md), expose it from
[AGENTS.md](../../AGENTS.md) and the grounding skill, and add a targeted
[Noetloom delivery skill](../../.agents/skills/noetloom-delivery/SKILL.md). The agent owns
commits, routine pushes, and CI diagnosis/repair for the already agreed scope. Routine
engineering choices remain with the agent. New commitments outside that scope retain
their own authority and resource requirements.

Keep specialized skills only where project facts change decisions: research/protocols,
evaluation/claims, artifact retention, and Git/CI delivery. Reuse the global engineering,
debugging, review, verification, and delegation skills rather than copying them into a
large Noetloom instruction collection. Add backend- or training-specific skills when actual
implementation and repeated workflows establish what they need to teach.

Completion requires the reviewed foundation and this authority correction to be pushed,
hosted Linux/macOS checks to pass, and the result to be recorded in the active plan's
delivery item. Skill behavior should be reviewed on a routine continuation request without
inserting another push-approval question.
