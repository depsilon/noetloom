# Noetloom research charter

Noetloom investigates whether compact learned machinery, persistent mutable state, and adaptive
computation can support a general-purpose alternative to today's large language models.
Language, code, perception, communication, and tool use are target capabilities of the system.
The intelligence is the research object; its architecture is not yet established.

## Intent and boundaries

The governing intent is the last of three founder-supplied design discussions, adopted on
2026-09-30. The progression moved from an original memory-first recurrent LLM, through a broader
cognitive system, to an experimental foundation architecture without a required LLM subsystem.
The earlier discussions remain sources of hypotheses and experimental discipline. Their proposed
parameter counts, six-module decomposition, fixed cognitive primitives, and illustrative 128 GB
hardware allocation are not adopted requirements. Private discussion exports are not republished.

The technical north star is substitution across the tasks people use LLMs for, followed by
capabilities such as durable learning and reusable learned computation. This is a research goal,
not a present capability claim, a market forecast, or a promise of frontier parity.

- Learn useful computational structures rather than prescribing a human taxonomy of thought.
- Separate knowledge, working state, reusable procedures, and foundational learned parameters when
  doing so measurably helps. Their final representation remains open.
- Co-design representations, training objectives, and execution around actual resource costs.
- Keep deployed learned components original and trained from their own initialization.
  Established tensor libraries and published algorithms remain legitimate tools.
- Treat pretrained systems as explicitly separated research references, comparisons, or permitted
  development/data assistance. Record teacher provenance and test contamination; they do not become
  hidden runtime cognition, embeddings, routing, or verification.
- Design for local execution. Budget training independently and scale only after throughput,
  memory, storage, and scientific value are measured.
- Develop openly, retain negative results, and make claims traceable to reproducible evidence.

## What transfers from ShardLoom

| ShardLoom mechanism | Noetloom hypothesis | Evidence needed |
| --- | --- | --- |
| Avoid irrelevant reads and early materialization | Select state before expensive computation; delay conversion to language | Quality versus measured end-to-end cost, including selection overhead |
| Reuse prepared state and execution structure | Retain associations and acquire reusable computation | New bindings, interference, unseen compositions, and ablations |
| Execute in useful representations | Learn representations that support operations without wasteful expansion | Representation changes preserve task quality and reduce real work |
| Policy-controlled resource scheduling | Learned proposals operate within deterministic run budgets | Useful compute allocation against fixed-budget controls |
| Workload-scoped evidence | Scope every result to its task, data, conditions, and provenance | Independent checks, held-out cases, uncertainty, and replay |

These transfers are research hypotheses. Database operation certificates can establish exact
semantics for specified operations; a cognitive trace does not establish arbitrary factual truth.
Vortex, Rust, ShardLoom's runtime, and its product-specific constraints are not mandatory dependencies.

## Progress means

A result changes a technical decision and survives appropriate controls. A coherent engineering
improvement can close infrastructure work; a capability claim requires learned-system evidence.
Documentation, execution traces, and hand-written reference solvers are useful infrastructure,
but do not count as learned intelligence. Broad capability requires a maintained profile spanning
language, coding, reasoning, retention, adaptation, multimodal transfer, and calibrated tool use.

The active implementation sequence lives only in [the plan](state/plan.json).
