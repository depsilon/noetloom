# Decision 0001: evidence before architecture scale

Date: 2026-09-30. Status: adopted for the research foundation.

## Decision

Create a small, dependency-free Python control plane before selecting a learned backend.
Adopt the final founder discussion as the charter: Noetloom itself is the experimental
foundation intelligence. Keep representation, memory, recurrence, and reusable computation
as testable mechanisms. Do not embed a mandatory pretrained LLM or a human cognitive taxonomy.

Use one machine-readable queue, concise agent entrypoints, targeted project skills, a
primary-source catalog, falsifiable hypotheses, registered protocols, bounded local storage,
and independently inspectable raw run evidence. General skill guidance remains global.
This transfers ShardLoom's evidence and continuity discipline without copying its product
runtime, large historical ledgers, or fixed phase machinery.

Start with a deterministic mutable-recall harness and explicit hand-written controls.
This exercises leakage boundaries, operation semantics, controls, artifact identity,
failure handling, and replay before learned models make errors harder to diagnose.
Its score establishes no learned capability. The next research item must introduce
a from-scratch learned candidate, credible matched baseline, and a learning protocol.

## Alternatives and tradeoffs

A full model stack now would force decisions about scale, backend, data, and components
without measured throughput or informative controls. A docs-only foundation would leave
artifact and verification conventions untested. The selected harness gives immediate,
bounded evidence while leaving the model design open.

The connected machine has 16 GiB RAM, so the previous discussion's illustrative 128 GB
budget is not adopted. No model weights or datasets are downloaded. Default run storage
is a 10 GiB unsynced working set with 20 GiB free-disk headroom; individual protocols
narrow the run limits. Git retains source and compact evidence. Durable checkpoint
hosting, publication authority, and code/data/model licenses remain explicit future decisions.

The runtime inventory covers the bootstrap's Python source. Replay is deterministic
evidence under matching code, not trusted attestation or independent validation of physical
resource measurements. Shared generator/scorer bugs require separate known-outcome tests.

## Research additions

The [hypothesis register](../research/hypotheses.json) adds reversible acquisition as a
candidate: separately test whether versioned temporary state and selective promotion
improve recovery from bad updates at equal total cost. This is an untested research idea
with unassessed novelty, not an architectural commitment or a claim of invention.

The [source catalog](../research/sources.json) records abstract-level primary-source leads
for memory, recall diagnostics, adaptive computation, program libraries, and plasticity.
Read methods and evaluation details before deriving the next model experiment.

Completion evidence will be linked from the completed N-001 item in the
[plan](../state/plan.json). Subsequent evidence does not revise the scope of this decision.
