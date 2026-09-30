# Contributing to Noetloom

Start with [AGENTS.md](AGENTS.md) and `python3 -B -m noetloom status`. Keep a change coherent:
include the implementation, relevant contracts, evidence, and the decision it changes.

For a research change, use the [research skill](.agents/skills/noetloom-research/SKILL.md)
and register the question and controls before evaluating. A failed, well-controlled
experiment is useful. Report it without scaling or changing the held-out task until it passes.

For runtime changes, run focused tests while editing, then:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B -m noetloom check
python3 -B scripts/rust.py check
python3 -B scripts/rust.py fixture
```

Run and replay EXP-0001 if generation, scoring, execution, storage, or verification changes.
CI covers Rust 1.98 plus Python 3.11 on Linux and Python 3.13 on macOS; a local pass does not establish
that hosted CI has run. No third-party Python package is needed by the bootstrap.
The Rust driver owns unsynced build storage and bounded fixture admission. For focused Cargo
work, set an admitted `CARGO_TARGET_DIR` first; do not build into the synced checkout.

Use the [artifact skill](.agents/skills/noetloom-artifacts/SKILL.md) before downloading
data or producing checkpoints. Do not add private discussion exports, credentials,
large generated files, or training data to Git. Record data rights and provenance before
reuse; reference citations do not grant rights to associated code, weights, or datasets.

Noetloom source and documentation use [Apache-2.0](LICENSE), selected by the owner.
Contributions are subject to its copyright and patent terms. Keep third-party licenses,
datasets, learned artifacts, branding, and patent strategy within the
[documented licensing boundaries](docs/licensing.md).
