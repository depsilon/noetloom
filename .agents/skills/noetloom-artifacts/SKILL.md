---
name: noetloom-artifacts
description: Plan or perform Noetloom data downloads, experiment-output storage, checkpoint archival, and local retention within explicit storage and publication limits.
---

# Noetloom artifacts

Read [storage and retention](../../../docs/storage.md), the
[resource policy](../../../config/resource-policy.json), and the selected protocol.
Run `python3 -B -m noetloom doctor` before a built-in run. Larger downloads or training
need an admitted resource plan including peak temporary space, not only final file size.

Keep bulk files outside the checkout and synced folders. Share one local run cache across
agents to preserve serialization. Admission reservations, sampled disk checks, and
cooperative deadlines are not OS quotas or a memory sandbox. Do not silently weaken the
policy, switch caches to evade a lock, or auto-remove a lock presumed stale.

Ordinary Git holds source, manifests, and compact evidence. Selected authorized project
assets may use Releases; LFS has separate accounting and is not enabled by default.
Recheck current provider limits before substantial transfers. Record provenance and rights
for data, code, weights, teacher assistance, and generated outputs separately.

For unique learned artifacts, establish retrievable durable bytes and verify their identity
before proposing local retirement. A manifest or the ability to retrain is not a backup.
Use content hashes, exact locations, and explicit retention decisions. No part of this
skill grants permission to publish, spend, or delete artifacts outside the user's authority.

If capacity is insufficient, report the admission reason and preserve the run. Complete
reversible preparation; do not launch an oversized job or silently discard evidence.
