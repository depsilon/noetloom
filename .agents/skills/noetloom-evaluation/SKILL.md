---
name: noetloom-evaluation
description: Implement or review Noetloom acquisition gates, development/final split isolation, learning telemetry, controls, replay evidence, budgets, and claim scope.
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

Distinguish optimization, same-format generalization, encoding interference and transfer.
Require task-appropriate acquisition evidence before interpreting a representation comparison;
use the staged development contract rather than inspecting final examples to tune a weak model.
Keep loss curves, training and validation accuracy, class/support counts and per-format results.
Tiny-set memorization is a sanity check. Loss, a finite gradient and one successful seed do
not establish reliable learning. Report unequal realized compute even under common ceilings.
Enforce advancement at the registered unit: an individually passing seed cannot admit
arm-level transformation tests when the contract requires every seed to acquire first.

For new learning workers, preserve fitting telemetry before downstream verification. Report
fitting, verification and resource admission separately, with unknown or interrupted states
kept explicit; no partial record upgrades a failed run to success. Confirm this boundary
with an injected post-fit verification failure. Label saved weights as inference parameter
snapshots unless full training state and an interrupted-versus-uninterrupted check support
an exact-resume claim. These are prospective requirements, not retroactive capabilities of
the EXP-0002/0003/0004 drivers. See the evaluation contract and
[artifact rules](../../../docs/storage.md).

Use the [command reference](../../../docs/reference/commands.md) for exact supported checks.
Passing `check` is structural evidence. Passing EXP-0001 is harness evidence. Neither is
evidence that a model learned, that a new architecture is novel, or that it replaces an LLM.

Retain artifact identities and state where complete evidence is retrievable. Explain
measurement scope and shared verifier/generator assumptions. If source changes, revalidate
the affected behavior and produce new evidence; do not relabel an old run as current.
