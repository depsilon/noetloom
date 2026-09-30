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

Before accumulating another campaign of unique learned artifacts, establish a verified second
copy of the existing irreplaceable evidence and a bounded backup/restore path for new outputs.
Use a separate failure domain; another directory on the same disk is only a local duplicate.
Restore a declared useful artifact bundle into an isolated directory, verify its inventory
and dependencies, and exercise inference/replay from the restored bytes. Record location,
retention, hashes, restore scope and limitations under the storage contract. If no authorized
destination exists, prepare the inventory and size/retention plan, then surface that specific
choice before new checkpoint accumulation. Documentation alone does not satisfy this gate.

Weights support inference replay, not exact optimizer continuation. Distinguish parameter
snapshots, resumable training state and persisted inference state. Preserve completed fitting
records even when later verification fails. A manifest or the ability to retrain is not a
backup; verify durable retrieval before proposing local retirement. No part of this skill
grants permission to publish, spend, or delete artifacts outside the user's authority.

If capacity is insufficient, report the admission reason and preserve the run. Complete
reversible preparation; do not launch an oversized job or silently discard evidence.
