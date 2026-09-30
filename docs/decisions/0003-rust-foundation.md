# 0003 — Rust foundation, open representations, and competing providers

Date: 2026-09-30. Local and hosted verification accepted; N-005 is complete.

## Decision

Retain the research charter and build the first executable foundation in Rust before selecting
a learned architecture. The core now implements versioned native state, selected payload reads,
shared parameterized operators, dynamic work graphs, transaction-local writes, and bounded
execution. A separate-process restart reproduces the committed result. This closes an
infrastructure prerequisite; the system has not yet learned cognition.

Keep semantic decisions above an explicit execution-provider boundary. The persistent JSON/CPU
implementation is a reference provider; a separately implemented in-memory provider exercises the
same executor. Neither storage layout nor the current low-level operation vocabulary defines
Noetloom's final representations. Unsupported provider operations fail explicitly.

The owner broadened the research horizon without replacing the immediate memory experiment.
H-006 through H-011 preserve questions about units beyond tokens, multiple native representations,
discovered intermediate computation, temporary executable structures, cross-representation
transfer, and learning problem representations. They remain horizon questions, not admitted
experiments or established claims. H-001 through H-005 retain their original mechanism scope.

Source and documentation use Apache-2.0, superseding the uncommitted MIT selection. Dataset,
checkpoint, branding, and patent-strategy boundaries remain [explicit](../licensing.md).

## Executable evidence

Full artifacts live under `NOETLOOM_CACHE`, defaulting to `~/.cache/noetloom`. The compact
[identity record](../evidence/N-005-2026-09-30.json) identifies the exact source, binary, and
artifact manifests. No learned weights, external dataset, or pretrained runtime was introduced.

| Check | Result and scope |
| --- | --- |
| Rust formatting, tests, Clippy | 24 tests pass; warnings denied; persistent-state failures, concurrency, provider conformance, and dynamic execution covered |
| Rust fixture | 7 executed nodes; one shared affine operator used twice; 2 activated payloads/62 bytes; 56 logical active-value bytes; 29 staged bytes |
| Inactive state | A 65,536-byte payload is not activated; a regression test removes an inactive blob and still reads the selected cell successfully |
| Commit and restart | Cell 1 advances to revision 2 with scalar value 3; a second process reads the same snapshot/value |
| Commit I/O | Separately admitted and reported; zero validation reads in the fixture; a regression case exercises refusal and accounting for deduplicated blob reads |
| Python checks | 54 tests, including source identity, completion-marker failure, registry horizon separation, and provider-evidence refusal |
| EXP-0001 replay | All 12,096 predictions replay under the changed Python source identity; no learned capability claim |
| Resource admission | Two compiler jobs; roughly 205 MiB allocated build output and 18 MiB dependency cache at the recorded fixture; 20 GiB local disk headroom preserved |

Run commands:

```sh
python3 -B scripts/rust.py check
python3 -B scripts/rust.py fixture
python3 -B -m unittest discover -s tests -v
python3 -B -m noetloom check
python3 -B -m noetloom doctor
python3 -B -m noetloom run experiments/EXP-0001/protocol.json
python3 -B -m noetloom verify-run RUN_DIRECTORY
```

The review repaired interrupted immutable-file publication, a premature success marker in the
driver, missing deduplication I/O accounting, and a test provider's unsupported-ID handling.
Regression tests exercise those boundaries. Pending partial files remain outside the immutable
hash namespace and count toward storage admission. A directory-sync failure after pointer
publication is explicitly reported as uncertain durability, not as a rolled-back transaction.

## ShardLoom trial and decision

An existing ShardLoom 0.3.2 binary ran three public SQL queries over 512 synthetic trace-shaped
rows. The first query prepared Vortex state; the next two reused its embedded source binding.
Independent reference results matched: total count 512, activated-row count 128, and four
operation groups of 128 rows, with nominal scalar work summing to 1,152 for `apply` and zero
for the other groups. Small JSONL exports make result checking independent of the engine's
summary claims. No sibling-repository changes or engine rebuild were needed.

```sh
python3 -B scripts/shardloom_probe.py --binary SHARDLOOM_BINARY --source-checkout SHARDLOOM_CHECKOUT
```

Retain this optional analytics adapter for further representative evidence workloads. Do not
adopt ShardLoom as the required cognitive-state provider from this result. The recorded binary
hash identifies what ran; the nearby source checkout is explicitly not a verified build binding.
The first adapter attempt retained correct query rows but failed its evidence check because it
looked for an unprefixed route field. The corrected adapter recognizes the actual public-facade
schema and reran all three queries in a fresh directory; both attempts remain available.

This route exposes useful execution metadata but emits no standalone certificate payload.
Its memory admission basis is `post_execution_descriptor_check_not_runtime_allocation_enforcement`,
and its envelope does not report complete route-total timing. Decode/materialization occurs at
the small JSONL compatibility sink. These are explicit evidence limits. The run records observed
process/preparation duration, but it is not a comparative benchmark, a memory-enforcement proof,
or a claim of provider superiority.

## Remaining proof gaps and next work

The JSON index is resident metadata; values and traces remain bounded but resident during a run.
Cooperative limits do not constrain arbitrary controller code or replace an OS memory sandbox.
Nominal scalar counts cover registered affine and selection work, not all CPU instructions;
controller and persistence overhead are included only in elapsed-time observations. The current
operator/control fixtures are hand-authored, and no training backend has been selected.

N-002 next registers a learned state-access/update hypothesis, backend preflight, matched controls,
held-out structures, and complete resource accounting through this runtime boundary. Representation
questions and later ShardLoom state-provider comparisons require their own explicit queue decisions.

## Hosted verification

Implementation commit `eca6525499e0caed8cca9576fb809199df8cf1af` passed
[Checks run 36692631575](https://github.com/depsilon/noetloom/actions/runs/36692631575)
on Linux/Python 3.11 and macOS/Python 3.13. Both jobs completed successfully on 2026-09-30,
including Python tests, repository contracts, pinned Rust formatting/tests/Clippy,
separate-process state restart, host admission, and EXP-0001 replay. N-005 is closed;
the next admitted work is the N-002 learning protocol and backend preflight.
