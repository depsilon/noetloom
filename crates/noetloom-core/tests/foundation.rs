use std::fs::{self, OpenOptions};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use noetloom_core::Result;
use noetloom_core::engine::{
    CellTarget, Control, Controller, Node, Operation, Provenance, Registry, RunLimits, RunView,
    execute,
};
use noetloom_core::operator::{Activation, Affine};
use noetloom_core::store::{Store, StoreLimits};
use noetloom_core::value::{CellRef, Value};

static SEQUENCE: AtomicU64 = AtomicU64::new(0);

struct Sandbox(PathBuf);
impl Sandbox {
    fn new() -> Self {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        Self(std::env::temp_dir().join(format!(
            "noetloom-test-{}-{nonce}-{}",
            std::process::id(),
            SEQUENCE.fetch_add(1, Ordering::Relaxed)
        )))
    }
    fn open(&self) -> Store {
        Store::open(&self.0, StoreLimits::default()).unwrap()
    }
    fn seed(&self, number: f32) -> Store {
        let store = Store::create(&self.0, StoreLimits::default()).unwrap();
        let mut transaction = store.transaction();
        transaction.write(1, None, dense(number), 1 << 20).unwrap();
        transaction
            .write(
                99,
                None,
                Value::Bytes {
                    data: vec![7; 8192],
                },
                1 << 20,
            )
            .unwrap();
        transaction.commit().unwrap();
        self.open()
    }
}
impl Drop for Sandbox {
    fn drop(&mut self) {
        if self.0.exists() {
            fs::remove_dir_all(&self.0).unwrap();
        }
    }
}
fn dense(number: f32) -> Value {
    Value::Dense { data: vec![number] }
}
fn reference(id: u64, revision: u64) -> CellRef {
    CellRef { id, revision }
}
fn provenance() -> Provenance {
    Provenance::ScriptedFixture {
        description: "Integration-test controller; no learned behavior".into(),
    }
}
fn registry() -> Registry {
    let mut registry = Registry::default();
    registry
        .register(
            "increment",
            Affine {
                input_dim: 1,
                output_dim: 1,
                weights: vec![1.0],
                bias: vec![1.0],
                activation: Activation::Identity,
            },
            provenance(),
        )
        .unwrap();
    registry
}
fn read(id: u64, cell: CellRef) -> Node {
    Node {
        id,
        operation: Operation::Read {
            target: CellTarget::Pinned { reference: cell },
        },
    }
}

#[test]
fn restart_and_pinned_snapshots_preserve_exact_revisions() {
    let sandbox = Sandbox::new();
    let original = sandbox.seed(2.0);
    let mut transaction = original.transaction();
    let second = transaction.write(1, Some(1), dense(4.0), 1024).unwrap();
    assert_eq!(transaction.read(second).unwrap(), dense(4.0));
    assert_eq!(
        transaction.read(reference(1, 1)).unwrap_err().code,
        "stale_reference"
    );
    let receipt = transaction.commit().unwrap();
    assert_ne!(receipt.before, receipt.after);
    assert_eq!(receipt.changed_cells, vec![reference(1, 2)]);
    assert_eq!(
        original.transaction().read(reference(1, 1)).unwrap(),
        dense(2.0)
    );
    let reopened = sandbox.open();
    assert_eq!(reopened.snapshot_id(), receipt.after);
    assert_eq!(reopened.transaction().read(second).unwrap(), dense(4.0));
    assert_eq!(
        reopened
            .transaction()
            .read(reference(1, 1))
            .unwrap_err()
            .code,
        "stale_reference"
    );
}

#[test]
fn stale_writers_and_busy_writer_lock_do_not_advance_state() {
    let sandbox = Sandbox::new();
    let first = sandbox.seed(1.0);
    let second = sandbox.open();
    let mut a = first.transaction();
    let mut b = second.transaction();
    a.write(1, Some(1), dense(2.0), 1024).unwrap();
    b.write(1, Some(1), dense(3.0), 1024).unwrap();
    let receipt = a.commit().unwrap();
    assert_eq!(b.commit().unwrap_err().code, "write_conflict");
    assert_eq!(sandbox.open().snapshot_id(), receipt.after);
    let lock = OpenOptions::new()
        .read(true)
        .write(true)
        .open(sandbox.0.join("WRITER.lock"))
        .unwrap();
    lock.try_lock().unwrap();
    assert_eq!(
        sandbox.open().transaction().commit().unwrap_err().code,
        "writer_busy"
    );
}

#[test]
fn opening_and_selected_reads_do_not_touch_inactive_payloads() {
    let sandbox = Sandbox::new();
    let store = sandbox.seed(1.0);
    let snapshot: serde_json::Value = serde_json::from_slice(
        &fs::read(
            sandbox
                .0
                .join("snapshots")
                .join(format!("{}.json", store.snapshot_id())),
        )
        .unwrap(),
    )
    .unwrap();
    let inactive = snapshot["cells"]["99"]["blob_sha256"].as_str().unwrap();
    // A missing inactive blob is stronger evidence than counting controller selections.
    fs::remove_file(sandbox.0.join("blobs").join(format!("{inactive}.json"))).unwrap();
    let reopened = sandbox.open();
    let mut transaction = reopened.transaction();
    assert_eq!(transaction.read(reference(1, 1)).unwrap(), dense(1.0));
    assert_eq!(transaction.read_metrics().payload_reads, 1);
    assert!(transaction.read_metrics().payload_bytes < 100);
    assert!(transaction.read(reference(99, 1)).is_err());
}

#[test]
fn corrupt_activated_payload_and_snapshot_are_rejected() {
    let sandbox = Sandbox::new();
    let store = sandbox.seed(1.0);
    let snapshot_path = sandbox
        .0
        .join("snapshots")
        .join(format!("{}.json", store.snapshot_id()));
    let snapshot: serde_json::Value =
        serde_json::from_slice(&fs::read(&snapshot_path).unwrap()).unwrap();
    let active = snapshot["cells"]["1"]["blob_sha256"].as_str().unwrap();
    fs::write(
        sandbox.0.join("blobs").join(format!("{active}.json")),
        b"{}",
    )
    .unwrap();
    assert_eq!(
        sandbox
            .open()
            .transaction()
            .read(reference(1, 1))
            .unwrap_err()
            .code,
        "hash_mismatch"
    );
    fs::write(snapshot_path, b"{}").unwrap();
    assert_eq!(
        Store::open(&sandbox.0, StoreLimits::default())
            .unwrap_err()
            .code,
        "hash_mismatch"
    );
}

#[test]
fn dropped_transactions_and_rejected_writes_leave_state_unchanged() {
    let sandbox = Sandbox::new();
    let store = sandbox.seed(1.0);
    {
        let mut transaction = store.transaction();
        assert_eq!(
            transaction
                .write(1, None, dense(4.0), 1024)
                .unwrap_err()
                .code,
            "write_conflict"
        );
        assert_eq!(
            transaction
                .write(1, Some(1), dense(4.0), 1)
                .unwrap_err()
                .code,
            "store_budget"
        );
        transaction.write(1, Some(1), dense(4.0), 1024).unwrap();
    }
    assert_eq!(sandbox.open().snapshot_id(), store.snapshot_id());
    assert_eq!(
        sandbox.open().transaction().read(reference(1, 1)).unwrap(),
        dense(1.0)
    );
}

#[test]
fn commit_budget_failure_preserves_pointer_and_does_not_write_blobs() {
    let sandbox = Sandbox::new();
    let original = sandbox.seed(1.0);
    let store = Store::open(
        &sandbox.0,
        StoreLimits {
            max_store_bytes: 1024,
            ..StoreLimits::default()
        },
    )
    .unwrap();
    let before = fs::read_dir(sandbox.0.join("blobs")).unwrap().count();
    let mut transaction = store.transaction();
    transaction.write(1, Some(1), dense(5.0), 1024).unwrap();
    assert_eq!(transaction.commit().unwrap_err().code, "store_budget");
    assert_eq!(sandbox.open().snapshot_id(), original.snapshot_id());
    assert_eq!(
        fs::read_dir(sandbox.0.join("blobs")).unwrap().count(),
        before
    );
}

#[test]
fn retained_interrupted_write_does_not_poison_immutable_publication() {
    let sandbox = Sandbox::new();
    let store = sandbox.seed(1.0);
    // Model a crash during a pending blob write. It is retained and counted,
    // but it cannot occupy the hash-named destination for a valid retry.
    let partial = sandbox.0.join("blobs/.pending-interrupted-fixture");
    fs::write(&partial, b"{\"kind\":").unwrap();
    let mut transaction = store.transaction();
    transaction.write(1, Some(1), dense(8.0), 1024).unwrap();
    transaction.commit().unwrap();
    assert_eq!(
        sandbox.open().transaction().read(reference(1, 2)).unwrap(),
        dense(8.0)
    );
    assert!(partial.exists());
}

struct Batch(Option<Vec<Node>>);
impl Controller for Batch {
    fn next(&mut self, view: &RunView<'_>) -> Result<Control> {
        Ok(if let Some(nodes) = self.0.take() {
            Control::Add(nodes)
        } else if view.pending_nodes == 0 {
            Control::Halt
        } else {
            Control::Continue
        })
    }
}

fn workflow() -> Vec<Node> {
    vec![
        read(1, reference(1, 1)),
        Node {
            id: 2,
            operation: Operation::Apply {
                operator: "increment".into(),
                input: 1,
            },
        },
        Node {
            id: 3,
            operation: Operation::Write {
                cell_id: 1,
                expected_revision: Some(1),
                input: 2,
            },
        },
    ]
}

#[test]
fn every_work_budget_rejects_without_committing() {
    let sandbox = Sandbox::new();
    let store = sandbox.seed(1.0);
    let registry = registry();
    for limits in [
        RunLimits {
            max_nodes: 1,
            ..RunLimits::default()
        },
        RunLimits {
            max_graph_bytes: 0,
            ..RunLimits::default()
        },
        RunLimits {
            max_scalar_ops: 0,
            ..RunLimits::default()
        },
        RunLimits {
            max_payload_bytes: 0,
            ..RunLimits::default()
        },
        RunLimits {
            max_active_value_bytes: 0,
            ..RunLimits::default()
        },
        RunLimits {
            max_staged_bytes: 0,
            ..RunLimits::default()
        },
        RunLimits {
            max_trace_bytes: 0,
            ..RunLimits::default()
        },
    ] {
        let error = execute(
            &store,
            &registry,
            &mut Batch(Some(workflow())),
            provenance(),
            limits,
        )
        .err()
        .unwrap();
        assert!(
            error.code == "run_budget" || error.code == "store_budget",
            "{error}"
        );
        assert_eq!(sandbox.open().snapshot_id(), store.snapshot_id());
    }
}

#[test]
fn operation_failure_after_a_staged_write_does_not_commit() {
    let sandbox = Sandbox::new();
    let store = sandbox.seed(1.0);
    let mut nodes = workflow();
    // The write output is a reference, which cannot be transformed as a dense value.
    nodes.push(Node {
        id: 4,
        operation: Operation::Apply {
            operator: "increment".into(),
            input: 3,
        },
    });
    let error = execute(
        &store,
        &registry(),
        &mut Batch(Some(nodes)),
        provenance(),
        RunLimits::default(),
    )
    .err()
    .unwrap();
    assert_eq!(error.code, "invalid_input");
    assert_eq!(sandbox.open().snapshot_id(), store.snapshot_id());
}

#[test]
fn commit_deduplication_reads_have_a_separate_enforced_budget() {
    let sandbox = Sandbox::new();
    let initial = sandbox.seed(1.0);
    let mut transaction = initial.transaction();
    transaction.write(2, None, dense(2.0), 1024).unwrap();
    transaction.commit().unwrap();
    let store = sandbox.open();
    let encoded_bytes = serde_json::to_vec(&dense(1.0)).unwrap().len() as u64;
    let limits = RunLimits {
        max_payload_bytes: encoded_bytes,
        max_commit_validation_bytes: 0,
        ..RunLimits::default()
    };
    let error = execute(
        &store,
        &registry(),
        &mut Batch(Some(workflow())),
        provenance(),
        limits,
    )
    .err()
    .unwrap();
    assert_eq!(error.code, "store_budget");
    assert_eq!(sandbox.open().snapshot_id(), store.snapshot_id());
    let limits = RunLimits {
        max_commit_validation_bytes: encoded_bytes,
        ..limits
    };
    let result = execute(
        &store,
        &registry(),
        &mut Batch(Some(workflow())),
        provenance(),
        limits,
    )
    .unwrap();
    assert_eq!(result.receipt.metrics.payload_reads, 1);
    assert_eq!(result.receipt.metrics.payload_bytes, encoded_bytes);
    assert_eq!(result.receipt.commit.validation_reads, 1);
    assert_eq!(result.receipt.commit.validation_bytes, encoded_bytes);
}

struct DelayedHalt(Batch);
impl Controller for DelayedHalt {
    fn next(&mut self, view: &RunView<'_>) -> Result<Control> {
        if view.last_completed == Some(3) {
            std::thread::sleep(Duration::from_millis(30));
        }
        self.0.next(view)
    }
}

#[test]
fn cooperative_deadline_after_staging_prevents_commit() {
    let sandbox = Sandbox::new();
    let store = sandbox.seed(1.0);
    let error = execute(
        &store,
        &registry(),
        &mut DelayedHalt(Batch(Some(workflow()))),
        provenance(),
        RunLimits {
            max_wall_millis: 20,
            ..RunLimits::default()
        },
    )
    .err()
    .unwrap();
    assert_eq!(error.code, "run_budget");
    assert_eq!(sandbox.open().snapshot_id(), store.snapshot_id());
}

struct UntilThree {
    next_id: u64,
    written: bool,
    emitted: bool,
}
impl Controller for UntilThree {
    fn next(&mut self, view: &RunView<'_>) -> Result<Control> {
        let node = if let Some(last) = view.last_completed {
            if self.emitted {
                return Ok(Control::Halt);
            }
            if self.written {
                self.emitted = true;
                Node {
                    id: self.next_id,
                    operation: Operation::Emit { input: last - 1 },
                }
            } else {
                let Value::Dense { data } = &view.values[&last] else {
                    panic!("expected scalar");
                };
                if data[0] < 3.0 {
                    Node {
                        id: self.next_id,
                        operation: Operation::Apply {
                            operator: "increment".into(),
                            input: last,
                        },
                    }
                } else {
                    self.written = true;
                    Node {
                        id: self.next_id,
                        operation: Operation::Write {
                            cell_id: 1,
                            expected_revision: Some(1),
                            input: last,
                        },
                    }
                }
            }
        } else {
            read(1, reference(1, 1))
        };
        self.next_id = node.id + 1;
        Ok(Control::Add(vec![node]))
    }
}

#[test]
fn dynamic_depth_reuses_parameters_and_produces_deterministic_traces() {
    let mut runs = Vec::new();
    for initial in [0.0, 2.0, 0.0] {
        let sandbox = Sandbox::new();
        let store = sandbox.seed(initial);
        let result = execute(
            &store,
            &registry(),
            &mut UntilThree {
                next_id: 1,
                written: false,
                emitted: false,
            },
            provenance(),
            RunLimits::default(),
        )
        .unwrap();
        assert_eq!(result.values[&result.emissions[0]], dense(3.0));
        assert_eq!(
            sandbox.open().transaction().read(reference(1, 2)).unwrap(),
            dense(3.0)
        );
        assert_eq!(result.receipt.metrics.payload_reads, 1);
        assert_eq!(result.receipt.operators.len(), 1);
        assert_eq!(
            result.receipt.metrics.trace_bytes,
            serde_json::to_vec(&result.receipt.trace).unwrap().len() as u64
        );
        runs.push(result.receipt);
    }
    assert_eq!(runs[0].metrics.executed_nodes, 6);
    assert_eq!(runs[1].metrics.executed_nodes, 4);
    assert_eq!(
        runs[0].operators["increment"].parameters_sha256,
        runs[1].operators["increment"].parameters_sha256
    );
    assert_eq!(runs[0].trace, runs[2].trace);
    assert_eq!(runs[0].commit.after, runs[2].commit.after);
}

#[test]
fn selection_activates_only_the_chosen_reference_and_breaks_ties_first() {
    let sandbox = Sandbox::new();
    let store = Store::create(&sandbox.0, StoreLimits::default()).unwrap();
    let mut transaction = store.transaction();
    transaction
        .write(
            0,
            None,
            Value::Dense {
                data: vec![1.0, 1.0],
            },
            1024,
        )
        .unwrap();
    transaction.write(1, None, dense(7.0), 1024).unwrap();
    transaction.commit().unwrap();
    let store = sandbox.open();
    let result = execute(
        &store,
        &Registry::default(),
        &mut Batch(Some(vec![
            read(1, reference(0, 1)),
            Node {
                id: 2,
                operation: Operation::Select {
                    scores: 1,
                    choices: vec![reference(1, 1), reference(99, 1)],
                },
            },
            Node {
                id: 3,
                operation: Operation::Read {
                    target: CellTarget::FromNode { node: 2 },
                },
            },
        ])),
        provenance(),
        RunLimits::default(),
    )
    .unwrap();
    assert_eq!(result.values[&3], dense(7.0));
    assert_eq!(result.receipt.metrics.payload_reads, 2);
    assert_eq!(result.receipt.trace[1].cell, Some(reference(1, 1)));
    assert_eq!(result.receipt.commit.before, result.receipt.commit.after);
}

#[test]
fn dangling_and_duplicate_nodes_are_rejected() {
    let sandbox = Sandbox::new();
    let store = sandbox.seed(1.0);
    for nodes in [
        vec![Node {
            id: 1,
            operation: Operation::Emit { input: 2 },
        }],
        vec![read(1, reference(1, 1)), read(1, reference(1, 1))],
        vec![],
    ] {
        let error = execute(
            &store,
            &registry(),
            &mut Batch(Some(nodes)),
            provenance(),
            RunLimits::default(),
        )
        .err()
        .unwrap();
        assert_eq!(error.code, "invalid_graph");
    }
    assert_eq!(sandbox.open().snapshot_id(), store.snapshot_id());
}
