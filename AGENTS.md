# Noetloom agent instructions

Noetloom researches an original foundation architecture: compact learned computation over
persistent, selectively activated state. Language is one target capability. The charter in
[docs/charter.md](docs/charter.md) owns product intent; implementation must earn capability claims.

## Start and resume

For substantive work, inspect `git status --short --branch`, then run
`python3 -B -m noetloom status`. Read the selected item in
`docs/state/plan.json` and only its referenced designs, protocols, and skills. After compaction,
resume the same work and authorization; do not restart intake or reread the entire research archive.

`docs/state/plan.json` is the only active queue. Supporting research and decisions explain it;
they do not silently authorize another queue. Complete a coherent item, record evidence and the
decision, and continue through its required verification. A failed hypothesis is a valid research
outcome when its experiment was sound. Do not turn it into an indefinite prototype.

## Work boundaries

- Preserve the user's current instructions and already granted authority. Local implementation,
  repairs, disposable tests, and the small built-in harness can proceed without repeated approval.
- Follow the user's global Git rules. A roadmap entry does not grant push, merge, release,
  paid-compute, or external-data publication authority. Record later standing grants once.
- Use the existing global engineering/research/review skills when relevant. Keep general guidance
  there, not duplicated in every Noetloom document.
- The primary owns research judgment, architecture, integration, and acceptance. Delegate bounded
  independent work under the global subagent routing policy; verify results. Serialize local
  resource-heavy jobs, including jobs started by different agents.
- Work in the current checkout unless isolation is needed. Preserve unrelated user changes.

## Research invariants

- The deployed intelligence must not secretly depend on pretrained LLMs, embeddings, rerankers,
  teachers, or model-based verifiers. Development assistance and separately labeled comparison
  systems are different roles. Record any training-data assistance and its provenance.
- Own initialized learned components and established numerical libraries are compatible.
  Attention, recurrence, graphs, and compression are hypotheses or tools, not ideological tests.
- Do not prescribe human categories of thought as the required learned primitive inventory.
- Keep exact controls, learned models, tools, and retrieved state distinct in results. A trace proves
  what ran, not that an unrestricted answer is true or that a latent state is interpretable.
- Reference papers support only their demonstrated scope. Record what was actually read.
  Test novelty, generalization, interference, and real resource cost instead of naming a combination
  of familiar mechanisms and claiming a breakthrough.
- Expand scope through a falsifiable protocol and an explicit queue decision. Do not substitute
  documentation volume, passing marker checks, or toy task scores for learned capability.

## Targeted routing

| Work | Read |
| --- | --- |
| Premise or architecture | `docs/charter.md`, `docs/architecture/research-program.md` |
| Research or a new experiment | `.agents/skills/noetloom-research/SKILL.md` |
| Evaluation, controls, results | `.agents/skills/noetloom-evaluation/SKILL.md` |
| Artifacts, downloads, training outputs | `.agents/skills/noetloom-artifacts/SKILL.md` |
| Agent continuity and authority | `docs/operating-model.md` |
| CLI or contract changes | `docs/reference/commands.md`, `noetloom/contracts.py` |

## Verification and storage

The bootstrap uses Python 3.11+ and the standard library. From the repo root:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B -m noetloom check
python3 -B -m noetloom doctor
```

Use focused tests while editing, then the full small suite and contract checks at completion.
The built-in harness is a local infrastructure test, not a learned-model benchmark. Larger
training or evaluation needs a resource-admitted protocol; do not launch it from a docs change.

Keep bulk output outside the checkout and synced folders. `config/resource-policy.json` owns
default budgets. The runner reserves output space, serializes writers, and records bounded runs;
its sampled checks are not an OS memory sandbox. Never delete a unique checkpoint merely because
a manifest exists. See `docs/storage.md` for integrity, archival, and retention rules.

Before handing off, update the queue evidence and unresolved work. Leave exact commands and
artifact identities; do not copy large transcripts into the active queue.
