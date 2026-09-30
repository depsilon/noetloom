# Semantic decisions and physical execution

Noetloom owns what an operation means and how learned decisions propose work. An execution
provider owns the physical work needed to carry it out. This boundary preserves the
[representation horizon](../research/hypotheses.json) and permits systems experiments without
letting a storage format define cognition.

The first executable boundary is intentionally small:

```text
controller (scripted fixture now; learned proposal later)
  -> native-value operation graph and run budgets
  -> ExecutionProvider + StateTransaction
       -> noetloom-json-cpu: immutable files and scalar f32 operations
       -> independent in-memory provider: conformance-test implementation
       -> future provider, admitted only for operations it actually supports
```

Read, select, affine transform, staged write, and emission are low-level mechanisms. They
are not a cognitive ontology or a sufficient intelligence architecture. Dense arrays, bytes,
and cell references are the initial storage vocabulary; future representations require
explicit versioning and tests, not conversion to text by default.

The executor requires exact revisions, transaction-local writes, explicit commit outcomes,
finite values, declared capabilities, and cooperative resource accounting. An unsupported
operation fails explicitly. There is no silent provider substitution or external execution.
Receipts identify the chosen provider, operator parameters and provenance, activated cell
revisions, graph work, payload reads, and commit. Provider claims need conformance evidence;
a descriptor or certificate is not self-authenticating proof of correctness.

The JSON/CPU provider is an inspectable reference implementation. Its index resides in
memory and grows with cell count. It decodes selected JSON payloads and retains all successful
node values until completion. These choices establish a testable baseline, not a claim that
this is the optimal persistent-state engine. Store limits count logical file bytes; the run
driver separately accounts for allocated filesystem space. Runtime value budgets count
logical payload bytes, not process RSS or allocator overhead.
Activation reads and commit-time validation reads have separate limits and receipt fields.
Deduplicating a staged write can require verifying an existing blob; that cost is charged to
commit validation even when the corresponding cell was not activated by the controller.

## ShardLoom earns each role separately

The near-term role is experimental infrastructure: curation metadata, trace queries,
evaluation aggregates, contamination/provenance analysis, and execution evidence. The
long-term role of physical cognition state is a different hypothesis. Neither makes Vortex
or ShardLoom mandatory for the Rust core or its tests.

Use the actual admitted ShardLoom route. Its public local workflow prepares compatibility
inputs into Vortex and executes supported native operations. Its older decoded
`local-source-runtime` diagnostic does not establish a Vortex-native integration. Check the
exact engine's capabilities and retain unsupported outcomes; do not implement missing SQL
through a hidden analytical engine.

The initial infrastructure probe is bounded to at most 1,000 deterministic trace-shaped
rows and three public query shapes: total count, a filtered count, and a grouped aggregate.
The rows contain episode, operation, model/fixture, seed, measured work, and outcome fields.
An independent standard-library reference computes exact expected rows. Capture input,
query, binary and source-checkout identities, output rows, route/certificate fields, elapsed
time, preparation costs when exposed, and all failures. Bound output to 8 MiB, total runtime
to 30 seconds, engine memory request to 1 GiB and parallelism to two; use the shared run lease.
No dependency installation, engine rebuild, large dataset, or remote execution is required.

Success establishes interoperability and evidence coverage for those queries. It does not
select ShardLoom for learned state or show speed, memory, or accuracy superiority. Compare
correctness, coverage, conversion/preparation, query work, resource use, and evidence quality
on representative workloads before adoption. Binary identity is authoritative for a trial;
a nearby checkout commit is context unless a build manifest actually binds that binary to it.

Later Noetloom workloads may expose useful changes in ShardLoom. Record a concrete workload
and result before proposing such changes through that project's own queue. Preserve its
Vortex-native and no-fallback identity; preserve Noetloom's freedom to choose representations
and execution providers. No sibling repository change is implied by this probe.
