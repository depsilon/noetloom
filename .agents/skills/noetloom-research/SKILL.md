---
name: noetloom-research
description: Design or revise Noetloom architecture hypotheses and experiments using primary evidence, falsifiable predictions, and the project's original learned-system charter.
---

# Noetloom research

Read the selected item from `python3 -B -m noetloom status`, then its references. For a
premise change, read the [charter](../../../docs/charter.md). For mechanism selection,
read the [research program](../../../docs/architecture/research-program.md) and relevant
entries in the [source catalog](../../../docs/research/sources.json).

Separate three things: what a source demonstrated, the mechanism proposed for Noetloom,
and the experiment that could falsify that transfer. The catalog's review depth matters:
an abstract is enough to identify a lead, not to reproduce methods or establish novelty.
Use local source first and current primary documentation for changing APIs or libraries.

Before execution, register observation/supervision boundaries, learned and hand-written
components, credible controls, held-out structures, selection rules, complete cost budgets,
independent seeds, acceptance criteria, and stop conditions under the
[evaluation contract](../../../docs/evaluation.md). Choose scale after a bounded preflight.
The current runner supports only harness validation; a learned protocol requires a new
validated contract and execution path.

Preserve the original learned-system goal. Do not introduce a pretrained model as hidden
runtime intelligence, or hard-code a human cognitive taxonomy as the learned primitive set.
Known algorithms and numerical libraries remain useful. Do not confuse a dictionary,
execution trace, procedure cache, or generated curriculum with learned capability.
If the user explicitly revises the premise, update the charter and experiment classification
before proceeding under the new scope; do not silently preserve an obsolete constraint or claim.

Record a scoped retain/revise/reject decision, including negative results and deviations.
Update the single [plan](../../../docs/state/plan.json) only when that decision changes work.
A failed registered experiment is not permission to expand compute until it wins.
