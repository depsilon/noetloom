---
name: project-deployment
description: Plan and verify a deployment with explicit target and environment, scoped user authority, external secret handling, preflight, health, rollback, and rehearsal boundaries.
---

# Deployment project guidance

Use this guidance when a project is prepared for or operated in a deployment target. Keep deployment proportional to the application and distinguish local preparation from external changes.

## Record in the project and architecture owners

- Name the target, environment, affected resources, operator, and intended user-visible result.
- Record the exact scope of user authority for external writes and any environment-specific constraints.
- Identify required secrets by purpose and source without recording their values; keep values in the target's approved external secret mechanism.
- Define preflight conditions, health signals, success criteria, rollback steps, and how repeated execution behaves.
- Describe a dry run or rehearsal and how its evidence differs from a real deployment.

## Implementation boundaries

- Keep credentials out of source, logs, generated artifacts, and command examples; do not expose secret values in diagnostics.
- Make preflight failures stop before external mutation wherever feasible, and report the failed condition clearly.
- Design deployment steps to be idempotent where possible and document steps that are not safely repeatable.
- Require explicit user scope for external writes; local dry runs and rehearsals do not authorize a real deployment.

## Verify

- Run preflight and a dry run or rehearsal, recording their results separately from real deployment evidence.
- Confirm health checks and success criteria can detect a failed or incomplete rollout.
- Exercise rollback or validate its documented recovery path, and check repeat execution behavior.
- Verify logs and artifacts contain no secret values and that deployment targets match the recorded environment.
