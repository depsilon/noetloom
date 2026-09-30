# First executable foundation slice

Status: implementation design for N-005. The [charter](../charter.md) owns the destination.
This slice establishes machinery needed to test that destination; it is not yet intelligence.

## Build order

Build persistent native state, selective activation, shared parameterized transformations,
and bounded dynamic execution in Rust before selecting and comparing a learned candidate.
Then integrate learning through that execution path. A convenient neural-memory model must
not substitute for the architecture merely because it is easier to benchmark.

The precursor's substrate, kernel, graph, simulator, and controller describe useful concerns.
They are not six compulsory modules. Its named cognitive primitives and optional LLM decoder
were superseded by the later requirement to learn useful structure without a prescribed
human taxonomy or an LLM foundation. Keep native representations, knowledge/parameter
separation, conditional work, reusable structure, and evidence as research requirements.

## Rust owns execution and state

The core Rust library owns state identity, persistence, activation, shared operator execution,
the dynamic work graph, and resource accounting. The [provider boundary](execution-providers.md)
separates those semantics from physical storage and computation. The existing Python commands remain a
research control plane and an independently labeled infrastructure harness. No pretrained
runtime or language-model subsystem is introduced.

The first numerical operator is a small validated affine transformation with an optional
nonlinearity. Test weights are explicitly labeled fixtures. Supporting parameterized
execution does not establish that parameters were learned. Choose the training backend
after the Rust interfaces and a bounded throughput probe exist. Rust libraries such as
[Candle](https://github.com/huggingface/candle) and [Burn](https://burn.dev/books/burn/)
provide numerical/training building blocks; their ready-made model architectures are not
requirements for Noetloom. A separate research tool may later use Python when justified.

## State and selective activation

State cells have opaque IDs, revisions, and native payloads: dense numeric arrays, bytes,
or references to other cells. These are storage representations, not semantic categories.
Payloads live in content-addressed immutable blobs. A small snapshot index binds IDs to
revisions and blobs. Opening the index must not materialize every payload.

An execution reads only cells explicitly activated by the controller. Reads validate size,
hash, and revision before exposing data. Metrics distinguish index metadata from payload
reads. A selection trace alone is insufficient: a test must show that a large inactive
payload is never read. The first index is in-memory metadata; this does not claim sublinear
index cost or bounded metadata for an arbitrarily large knowledge store.

Writes remain transaction-local until successful completion. Commit produces new blobs and
a new snapshot, then atomically advances the current snapshot pointer. A failed execution
must leave persistent state unchanged. Concurrent writers must conflict explicitly; readers
may retain a pinned prior snapshot. Historical blobs and snapshots are retained. Garbage
collection and retirement of unique state are outside this slice.

## Shared transformations and dynamic execution

An operator registry separates reusable parameters from mutable state. Operators consume
native values and produce native values, with validated shapes and finite numbers.
One operator can execute repeatedly at different graph nodes; depth does not require
duplicating its parameters.

The controller proposes graph nodes as execution proceeds. The executor provides low-level
activation, selection, transformation, proposed writes, and emission. Dependency resolution
and resource enforcement are deterministic. No built-in node represents analogy, planning,
induction, truth, or another human cognitive category.

A controller can inspect completed results, add work, branch, or halt. Initial infrastructure
controllers are labeled scripted fixtures. A learned controller must later propose useful
work through the same boundary. Tests distinguish dynamic graph construction and bounded
iteration from learned allocation of computation; the former is necessary but not sufficient.

Each run limits submitted/executed nodes, graph bytes, nominal scalar operations, activation
payload I/O, commit validation I/O, active values, staged writes, trace size, and elapsed time.
Commit validation reads for deduplicated blobs are separate from controller activation reads.
Limits are checked before the relevant
work and between operations. They do not provide an OS memory sandbox or arbitrary-code
sandbox. The runtime executes registered operators, not generated native code.

## First vertical slice and acceptance

A restartable example initializes a few native cells, activates selected cells, applies a
shared transform, constructs additional work from observed output, commits a changed cell,
reopens the store, and validates the persisted result. The same executable must report its
operator provenance, source/build identity, snapshot IDs, executed graph, and resource counts.

Acceptance includes manual small-matrix outcomes, variable work without extra parameters,
untouched inactive payloads, exact restart behavior, stale revision refusal, corrupt blob
refusal, concurrent commit refusal, budget failures without commit, and deterministic
execution traces for the fixture. Cargo tests, formatting, linting, the existing Python
checks, and hosted Linux/macOS checks close the infrastructure item.

Only after this path exists does N-002 register a learned controller/state-update hypothesis,
training method, controls, held-out tasks, and measured budgets. N-003 tests variable
computation or learned reuse based on the observed limitation. Neither stage is replaced
by a manually programmed cognitive procedure that already knows the task's answer.

## Resource admission

Use the pinned Rust 1.98 toolchain, at most two compiler jobs, and an unsynced build
directory under `~/.cache/noetloom-tooling`. Admit at most 4 GiB of build artifacts and
512 MiB of dependency-cache storage while preserving 20 GiB free disk. The installed
toolchain is separate (about 1.5 GiB across existing toolchains at admission); do not remove
other toolchains. Each build command has a 300-second deadline. No model or dataset
download is needed. Serialize local builds and experiment jobs. Tiny disposable test stores
and fixture evidence remain bounded; complete persistent research artifacts are never
automatically evicted. Runtime trials and builds use the shared Noetloom run-cache lease.
The driver reserves 10 MiB for fixture state/receipts, checks current Rust source against the
binary's embedded manifest, and validates the result in a separate process. CI explicitly
uses the disposable `ci-smoke` disk-headroom profile; local runs retain the 20 GiB default.
