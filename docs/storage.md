# Storage, execution, and retention

## Separate durable knowledge from the local working set

| Store | Contents | Retention meaning |
| --- | --- | --- |
| Ordinary Git | Source, docs, protocols, small result summaries, hashes and retrieval manifests | Reviewed project history; deliberately small |
| GitHub Release assets, when authorized | Selected project checkpoints or evidence bundles, versioned and checksummed | Distribution of chosen project artifacts; verify retrieval before local retirement |
| Actions artifacts | Temporary CI diagnostics and evidence | Retention expires; deletion of a run also deletes its artifacts |
| Local unsynced cache | Active runs, staged downloads, reproducible temporary files | Bounded working set; no unique artifact is evicted automatically |
| External object storage, if later selected | Larger datasets/checkpoint history | Requires an explicit provider, rights, cost, and retention decision |

GitHub warns for ordinary files above 50 MiB and blocks files above 100 MiB. Noetloom sets
a much smaller working-file limit because Git history is replicated into local clones.
See [GitHub's large-file guidance](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).
Git LFS stores pointers in Git but has separate storage and bandwidth accounting; it is
not enabled by default. See [Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage).

GitHub documents up to 1,000 assets per Release and an individual asset size below 2 GiB.
Use Releases for selected project artifacts, not as an assumed unlimited training-data lake.
Recheck terms and limits before a large publication. See
[Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) and
[Actions artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts).

## Local admission

The [policy](../config/resource-policy.json) owns numeric limits. The default `local-small`
profile allows 10 GiB in the run cache, requires 20 GiB free disk after reserving output,
and caps an individual run at 64 MiB, 120 seconds, and 10,000 query cases. Each protocol
can narrow these limits. EXP-0001 narrows them to 8 MiB and 30 seconds.

Hosted CI explicitly selects [ci-smoke](../config/resource-policy-ci.json): a 64 MiB cache,
8 MiB run output, 30-second deadline, and 512 MiB disk headroom. This accounts for standard
[GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
whose documented storage is 14 GB. It does not change or automatically replace the local
profile. Do not use a different profile to bypass an admission failure on the working machine.

`NOETLOOM_CACHE` or `--cache` can select a dedicated root. The default is `~/.cache/noetloom`.
The guard refuses the checkout, its ancestors, home itself, filesystem root, and on macOS
Documents, Desktop, and standard iCloud/CloudStorage paths, checking lexical and resolved
paths. Custom sync clients and mounted remote filesystems are not exhaustively detectable:
choose an unsynced root. `.gitignore` controls Git, not cloud synchronization.

`doctor` checks admission without creating directories. `run` acquires an exclusive cache
lock, rechecks capacity, writes a fresh run directory, enforces bytes before each write,
checks its deadline during evaluation, and samples disk headroom. A lock is never removed
merely because it appears old. Inspect its owner and run before deliberately clearing it.

Reservations are admission calculations, not preallocated disk blocks. The cache inventory
refuses symlinks and special files; it conservatively counts the greater of logical and
allocated bytes and deduplicates hardlinks. It is not a filesystem quota. Other processes
can consume disk between samples. Deadlines are cooperative; process peak RSS is reported
but no OS memory limit is enforced. The EXP-0001 harness launches no external training process.

EXP-0002's separate driver serializes each training process and verification through the
same lease. Each run reserves 16 MiB, caps 120 seconds, checks the process group's sampled
RSS against 2 GiB, and checks the worker's final OS high-water RSS. It terminates a worker
that exceeds admission; sampling is still not an OS memory sandbox. Optional CPU training
dependencies reserve 1 GiB installed plus 256 MiB download space under the tooling cache.
Temporary installation staging counts against installed space; downloads are counted
separately in a single classification pass. Setup failures and verified wheel identities
are retained. No trained checkpoint is automatically evicted or publicly licensed.

EXP-0003 uses the same 16 MiB/120-second/2 GiB per-run admissions and shared lease. Its
preflight retains the compiled native executable as well as frozen data and parent identities.
There are five gate-fitting attempts. Each run stays below 10,000 query presentations;
its three-policy replay is a separate admitted run. Previous checkpoints and their parent
run manifests remain unchanged. All retained weights are local, not a public weight release.

EXP-0004 uses the same lease with 32 MiB/120-second/2 GiB per-run admissions and twenty
arm/seed attempts, including failures. It preserves the native executable, initial and all
validation checkpoints, selected weights, raw predictions and intermediate states. A failed
attempt remains failed even if a later audit verifies some retained predictions.

The shared training supervisor samples directories while native state writers may atomically
rename temporary pointer files. Live byte scans tolerate entries that disappear between
enumeration and inspection; these samples are approximate. They still reject symlinks,
special files and other I/O failures. After the worker exits, strict output/workspace scans
and artifact inventories are required before any successful completion manifest is written.
This avoids treating atomic publication as corruption without relaxing final admission.

## Artifact identity and retirement

Every complete harness run has a protocol, resource-policy snapshot, runtime source inventory,
raw predictions, report, and manifest. The manifest lists each payload's size and SHA-256.
It is written last. Missing or unexpected files, differing runtime source, changed predictions,
or invented scores cause replay verification to fail. A failed control-sensitivity result
is complete negative evidence, not a successful harness.

Checksums detect change relative to a manifest; they are not signatures or trusted attestation.
Replay checks the observable harness computation. It does not independently measure the
recorded wall time, machine details, peak RSS, or historical authorship. Preserve the source
revision or exact runtime files needed to replay archived runs.

Before retiring a unique learned checkpoint or important run:

1. Identify exactly which artifact is unique, its role, rights, source, protocol, and dependencies.
2. Produce a manifest with byte counts, content hashes, and a durable retrieval location.
3. Transfer only within existing publication authority. Verify the remote bytes through an
   independent read-back or provider-supported checksum with known semantics.
4. Record the verification and retention decision. Remove only the explicitly selected local
   artifact after the durable copy is established and retirement is authorized.

A manifest without retrievable bytes is not a backup. The ability to retrain is not proof
that a stochastic checkpoint can be reproduced exactly. No upload, eviction, or cleanup
daemon is part of this bootstrap. Stream or generate datasets where possible, with version,
license, transformation, and content manifests; retain minimal fixtures in Git.
