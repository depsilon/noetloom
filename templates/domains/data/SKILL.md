---
name: project-data
description: Build a small data workflow with documented source provenance, schema and grain, explicit null and duplicate policies, and reconciled deterministic outputs.
---

# Data project guidance

Use this guidance for importing, transforming, validating, or exporting data. Start with the smallest suitable tools; Spark, a database, or a hosted service is not required.

## Record in the project and architecture owners

- Identify each source, its provenance, access method, version or freshness, and permitted use.
- Define schema, types, units, keys, and row grain at input and output boundaries.
- State how null, invalid, and duplicate records are treated, including whether they are rejected, retained, or resolved and by what rule.
- Specify transformation ordering, deterministic output expectations, and reconciliation measures such as row counts and key totals.
- Describe expected behavior for reruns and partial failures, including which outputs may be published locally.

## Implementation boundaries

- Validate source structure and assumptions before transformation; preserve enough context to diagnose rejected records.
- Make transformations reproducible and avoid hidden dependence on row order, current time, or mutable external state.
- Do not conceal dropped, duplicated, or changed records; expose counts and reasons for material exclusions.
- Keep raw inputs intact and make output replacement behavior explicit.

## Verify

- Use small fixtures with known reference outputs, including nulls, duplicates, malformed rows, and boundary values relevant to the policy.
- Check schema, grain, deterministic results, and idempotence across repeated runs.
- Reconcile input, accepted, rejected, and output row counts and relevant totals or keys.
- Exercise partial-failure behavior and confirm reruns do not produce mixed or misleading outputs.
