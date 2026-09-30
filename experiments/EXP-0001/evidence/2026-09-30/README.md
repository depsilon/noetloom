# EXP-0001 bootstrap evidence

Decision: the mutable-recall harness passed its registered controls and deterministic
replay on 2026-09-30. This closes infrastructure item N-001. It demonstrates no learning,
persistent cross-session cognition, general intelligence, or advantage over an LLM.

## Identity and retention

- Run ID: `20260930T023155Z-6a45c94644`
- Source commit: `b559aaaf5fe62b1f49f5f4e6b504e7139660d741`; worktree clean at execution
- Runtime source digest: `2b951206cfb0ee257606e2e3fccb0a88d257ac5f2f6597eb193878b2ae32f887`
- Manifest SHA-256: `26899b1b7b2fa4a43fd1e641b6f0c0004b4bdbf407adeea7f2fb0ef4a41219d5`
- Complete run bytes: 1,991,014, retained at `~/.cache/noetloom/20260930T023155Z-6a45c94644`
- Host: macOS arm64, Python 3.13.13, `local-small` profile

This directory retains the exact [manifest](manifest.json), [report](report.json), and
[source inventory](source.json), totaling 16,076 bytes. It is a compact evidence record,
not a complete run directory. Raw predictions and protocol/policy snapshots remain in the
local cache. No remote run archive has been uploaded or verified. Do not describe the
machine-local payloads as retrievable from GitHub.

The [registered protocol](../../protocol.json) and source can generate a new equivalent
prediction stream. A new run has its own identity, timestamps, environment observations,
and manifest hash. Regeneration does not preserve the original physical measurements.

## Result

144 episodes across three seeds produced 3,024 query cases and 12,096 control predictions.
All six acceptance checks passed. Replay verified every prediction and the complete score
structure, including split/phase results and observation-stream fingerprints.

| Hand-written control | Correct / total | Accuracy |
| --- | --- | --- |
| Exact memory | 3,024 / 3,024 | 100% |
| No memory | 432 / 3,024 | 14.29% |
| Stale memory | 2,448 / 3,024 | 80.95% |
| Bounded memory | 1,488 / 3,024 | 49.21% |

Absent memory failed all known-value probes; stale memory failed revision and deletion
probes; bounded memory failed delayed recall under capacity pressure. Complete episode
observation streams were disjoint. These results diagnose the specified control behavior.

The runner recorded 0.0340 seconds before report serialization and a whole-process peak RSS
of 26,836,992 bytes. These are observations of a tiny hand-written harness, not a model
benchmark or end-to-end performance comparison. No OS memory limit was enforced.

## Verification and review

Executed from the source checkout:

```sh
python3 -B -m unittest discover -s tests -q
python3 -B -m noetloom check
python3 -B -m noetloom doctor
python3 -B -m noetloom run experiments/EXP-0001/protocol.json
python3 -B -m noetloom verify-run ~/.cache/noetloom/20260930T023155Z-6a45c94644
```

All 48 tests passed. Repository contracts, references, syntax, and working-file budgets
passed. The five skill files (three repo-local skills, versioned grounding entrypoint,
and installed local wrapper) passed the bundled skill validator. The YAML-only developer
validator dependency was PyYAML 6.0.3 in an external tooling cache; the harness itself uses
only Python's standard library.

An independent review found and verified fixes for macOS case-alias cache containment,
source provenance across imported checkouts, and malformed oversized JSON integers.
Eight focused regression tests and the original reproductions passed in the follow-up;
the review reported no remaining blocker in that scope. Runner integration tests now
execute fresh CLI processes from their own fixture checkouts.

Skill scenarios covered resuming after compaction, attempted retirement backed only by
a manifest, and a user-requested change to pretrained runtime assistance. Guidance preserves
existing authority, complete artifact bytes, and accurate experiment classification.
This is behavioral review, not a measured claim of optimal agent performance.

The CI workflow's YAML, triggers, permissions, matrix, explicit `ci-smoke` profile, and
inline Python syntax were checked locally. Action commit pins were verified through
official GitHub release/commit endpoints. Hosted Linux/macOS CI had not run at the time
of this local evidence record. The later
[delivery evidence](../../../../docs/decisions/0002-autonomous-delivery.md#delivery-evidence)
records the workflow correction and passing Linux Python 3.11/macOS Python 3.13 checks.

## Next decision

Proceed through N-002's methods review, resource preflight, and learning-protocol registration
before training the first original candidate against a credible matched learned baseline.
The five architecture hypotheses remain proposed; EXP-0001 supports none of them as learned
capability evidence. See the [active plan](../../../../docs/state/plan.json) and
[foundation decision](../../../../docs/decisions/0001-foundation.md).
