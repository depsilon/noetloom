---
name: noetloom-runtime
description: Implement or review Noetloom Rust state, execution-provider boundaries, dynamic work, transaction integrity, and bounded infrastructure evidence without confusing fixtures with learned capability.
---

# Noetloom runtime

Read the active queue item and its [foundation design](../../../docs/architecture/foundation-runtime.md)
and [provider boundary](../../../docs/architecture/execution-providers.md). The Rust core owns
execution and state contracts; Python remains the research/control plane. Preserve the
charter's broader representation questions. No LLM, fixed cognitive taxonomy, or sibling
storage format is a mandatory intelligence substrate.

Keep controllers, registered parameters, mutable native state, and physical providers distinct.
Scripted controllers and hand-authored weights must identify themselves as fixtures. New
providers must preserve operation semantics, revision checks, staged writes, failure behavior,
and explicit unsupported outcomes. Do not substitute an exact lookup or precomputed helper
for a learned proposal or an actual provider execution.

For changes, test the affected failure boundary: inactive payload reads, revision/hash checks,
concurrent commits, failure after staging, resource refusal, dynamic work, and provider
conformance. A persistent-state path needs a separate-process restart check. Resource claims
must distinguish logical values, serialized payloads, allocated files, nominal scalar work,
observed time, and process memory. Cooperative checks are not an OS sandbox.

Use `python3 -B scripts/rust.py check` and `python3 -B scripts/rust.py fixture` for complete
Rust verification. The driver serializes with other Noetloom runs, limits compiler jobs,
and keeps builds/dependencies/state outside synced folders. For a focused Cargo command,
set `CARGO_TARGET_DIR` to the admitted unsynced tooling directory first. Do not run bare
Cargo builds into the checkout. Preserve unique state and failed-run evidence.

Keep Rust source/build identity separate from the Python harness inventory. After final
source changes, regenerate fixture evidence with the current binary, verify its embedded
source identity, and record exact artifacts and limitations. Follow the
[delivery skill](../noetloom-delivery/SKILL.md) through hosted checks under the standing grant.
