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

## Delivery evidence

The foundation and standing authority are published on `depsilon/noetloom`'s `main` branch.
Commit `866fc795a77e4b2016fedaf35dba2c0e04b95a27` passed
[Checks run 36685300250](https://github.com/depsilon/noetloom/actions/runs/36685300250)
on 2026-09-30. Both jobs completed successfully:

| Hosted environment | Unit tests | Repository contracts | Host admission | EXP-0001 replay |
| --- | --- | --- | --- | --- |
| Ubuntu, Python 3.11 | 48 passed | Passed | `ci-smoke` passed | 12,096 predictions verified |
| macOS, Python 3.13 | 48 passed | Passed | `ci-smoke` passed | 12,096 predictions verified |

Both runs used runtime source digest
`2b951206cfb0ee257606e2e3fccb0a88d257ac5f2f6597eb193878b2ae32f887`, matching the
[local bootstrap evidence](../../experiments/EXP-0001/evidence/2026-09-30/README.md).
The hosted runs are disposable infrastructure checks. Their full run payloads were not
archived; hosted logs are subject to retention. This establishes tested platform compatibility
and deterministic harness behavior, not learned capability.

The [first workflow attempt](https://github.com/depsilon/noetloom/actions/runs/36685079493)
was rejected before any job ran: `runner.temp` is unavailable in a job-level `env` expression.
Moving the cache setting to the two execution steps follows GitHub's
[context availability rules](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability).
The successful run above verifies the correction without removing a check or changing a budget.

The delivery skill passed the skill validator and an independent behavioral review of
resuming work, repairing CI, and pushing the fix under the standing grant. The authority
review found no unresolved issue. N-004 is complete; the next research item remains N-002,
beginning with methods review and a registered learning protocol.
