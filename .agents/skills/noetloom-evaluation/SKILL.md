---
name: noetloom-evaluation
description: Implement or review Noetloom experiment controls, scoring, replay evidence, comparison budgets, and the scope of reported research claims.
---

# Noetloom evaluation

Read the relevant protocol and [evaluation contract](../../../docs/evaluation.md).
Determine which claim is under test: infrastructure, learned mechanism, transfer,
continual adaptation, or broad capability. Apply evidence appropriate to that claim.

For the bootstrap, preserve scorer/control separation, reset boundaries, actual-input
overlap detection, known expected operation outcomes, and sensitive negative controls.
Verify raw predictions and summaries by replay. Recomputed manifest hashes alone must
not make fabricated predictions or scores pass. Test malformed, incomplete, and
resource-refused runs when changing those paths.

For learned candidates, match information access and training/tuning/inference resources.
Charge routing, failed search, retrieval, acquisition, and verification. Inspect held-out
structure as well as seed separation. Keep per-seed and per-task results; uncertainty
must respect correlated queries and the true independent unit. Report failed runs and
selection history instead of retaining only successful seeds.

Use the [command reference](../../../docs/reference/commands.md) for exact supported checks.
Passing `check` is structural evidence. Passing EXP-0001 is harness evidence. Neither is
evidence that a model learned, that a new architecture is novel, or that it replaces an LLM.

Retain artifact identities and state where complete evidence is retrievable. Explain
measurement scope and shared verifier/generator assumptions. If source changes, revalidate
the affected behavior and produce new evidence; do not relabel an old run as current.
