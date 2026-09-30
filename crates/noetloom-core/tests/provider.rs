use std::cell::{Cell, RefCell};

use noetloom_core::engine::{
    CellTarget, Control, Controller, Node, Operation, Provenance, Registry, RunLimits, RunView,
    execute,
};
use noetloom_core::operator::{Activation, Affine};
use noetloom_core::provider::{
    Capability, ExecutionProvider, ProviderDescriptor, StateTransaction,
};
use noetloom_core::store::{CommitReceipt, ReadAdmission, ReadMetrics, sha256};
use noetloom_core::value::{CellRef, Value};
use noetloom_core::{Error, Result};

#[derive(Clone)]
struct MemoryCell {
    revision: u64,
    value: Value,
}

struct MemoryProvider {
    cell: RefCell<MemoryCell>,
    affine_calls: Cell<u64>,
    capabilities: Vec<Capability>,
}

impl MemoryProvider {
    fn new(capabilities: Vec<Capability>) -> Self {
        let value = Value::Dense { data: vec![2.0] };
        Self {
            cell: RefCell::new(MemoryCell { revision: 1, value }),
            affine_calls: Cell::new(0),
            capabilities,
        }
    }

    fn current(&self) -> (u64, Value) {
        let cell = self.cell.borrow();
        (cell.revision, cell.value.clone())
    }
}

struct MemoryTransaction<'a> {
    provider: &'a MemoryProvider,
    pinned: MemoryCell,
    staged: Option<MemoryCell>,
    staged_bytes: u64,
    reads: ReadMetrics,
}

impl StateTransaction for MemoryTransaction<'_> {
    fn read_admission(&self, reference: CellRef) -> Result<ReadAdmission> {
        reference.validate()?;
        let current = self.staged.as_ref().unwrap_or(&self.pinned);
        if reference.id != 1 || reference.revision != current.revision {
            return Err(Error::new(
                "stale_reference",
                "cell is absent at the requested pinned revision",
            ));
        }
        Ok(ReadAdmission {
            payload_bytes: if self.staged.is_some() {
                0
            } else {
                current.value.logical_bytes()?
            },
            value_bytes: current.value.logical_bytes()?,
        })
    }

    fn read(&mut self, reference: CellRef) -> Result<Value> {
        let admission = self.read_admission(reference)?;
        let current = self.staged.as_ref().unwrap_or(&self.pinned);
        let value = current.value.clone();
        if admission.payload_bytes > 0 {
            self.reads.payload_reads += 1;
            self.reads.payload_bytes += admission.payload_bytes;
        }
        Ok(value)
    }

    fn write(
        &mut self,
        id: u64,
        expected: Option<u64>,
        value: Value,
        max_staged_bytes: u64,
    ) -> Result<CellRef> {
        if id != 1 {
            return Err(Error::new(
                "unsupported_operation",
                "this test provider only implements existing cell 1",
            ));
        }
        let actual = if id == 1 {
            Some(self.staged.as_ref().unwrap_or(&self.pinned).revision)
        } else {
            None
        };
        if actual != expected {
            return Err(Error::new(
                "write_conflict",
                "write expectation does not match pinned or staged revision",
            ));
        }
        value.validate(u64::MAX)?;
        let next_staged_bytes = value.logical_bytes()?;
        if next_staged_bytes > max_staged_bytes {
            return Err(Error::new("store_budget", "staged writes exceed budget"));
        }
        let revision = expected
            .unwrap_or(0)
            .checked_add(1)
            .ok_or_else(|| Error::new("write_conflict", "revision exhausted"))?;
        self.staged = Some(MemoryCell { revision, value });
        self.staged_bytes = next_staged_bytes;
        Ok(CellRef { id, revision })
    }

    fn staged_bytes(&self) -> u64 {
        self.staged_bytes
    }

    fn read_metrics(&self) -> &ReadMetrics {
        &self.reads
    }

    fn commit(self, _max_validation_bytes: u64) -> Result<CommitReceipt> {
        let mut live = self.provider.cell.borrow_mut();
        if live.revision != self.pinned.revision {
            return Err(Error::new(
                "write_conflict",
                "provider revision advanced since transaction began",
            ));
        }
        let before = format!("memory-rev-{}", live.revision);
        let (generation, changed_cells) = if let Some(staged) = self.staged {
            let reference = CellRef {
                id: 1,
                revision: staged.revision,
            };
            *live = staged;
            (live.revision, vec![reference])
        } else {
            (live.revision, vec![])
        };
        let after = format!("memory-rev-{generation}");
        Ok(CommitReceipt {
            before,
            after,
            generation,
            changed_cells,
            new_file_bytes: 0,
            validation_reads: 0,
            validation_bytes: 0,
            reads: self.reads,
        })
    }
}

impl ExecutionProvider for MemoryProvider {
    type Transaction<'a> = MemoryTransaction<'a>;

    fn descriptor(&self) -> ProviderDescriptor {
        ProviderDescriptor {
            name: "test-memory".into(),
            version: "1".into(),
            representations: vec!["dense_f32".into()],
            capabilities: self.capabilities.clone(),
            atomic_commit: true,
            revision_checked: true,
            external_execution: false,
        }
    }

    fn metadata_bytes_read(&self) -> u64 {
        0
    }

    fn begin(&self) -> Result<Self::Transaction<'_>> {
        let pinned = self.cell.borrow().clone();
        Ok(MemoryTransaction {
            provider: self,
            pinned,
            staged: None,
            staged_bytes: 0,
            reads: ReadMetrics::default(),
        })
    }

    fn affine(&self, operator: &Affine, input: &Value) -> Result<Value> {
        self.affine_calls.set(self.affine_calls.get() + 1);
        operator.apply(input)
    }

    fn select(&self, scores: &Value, choices: &[CellRef]) -> Result<CellRef> {
        let Value::Dense { data } = scores else {
            return Err(Error::new(
                "invalid_input",
                "selection scores must be dense",
            ));
        };
        if data.is_empty()
            || data.len() != choices.len()
            || data.iter().any(|score| !score.is_finite())
        {
            return Err(Error::new(
                "invalid_input",
                "selection requires matching finite scores and choices",
            ));
        }
        let mut selected = 0;
        for (index, score) in data.iter().enumerate().skip(1) {
            if *score > data[selected] {
                selected = index;
            }
        }
        choices[selected].validate()?;
        Ok(choices[selected])
    }
}

fn all_capabilities() -> Vec<Capability> {
    vec![
        Capability::Read,
        Capability::Select,
        Capability::Affine,
        Capability::Write,
    ]
}

fn affine() -> Affine {
    Affine {
        input_dim: 1,
        output_dim: 1,
        weights: vec![2.0],
        bias: vec![1.0],
        activation: Activation::Identity,
    }
}

fn registry() -> Registry {
    let mut registry = Registry::default();
    registry
        .register(
            "double_plus_one",
            affine(),
            Provenance::ScriptedFixture {
                description: "conformance fixture".into(),
            },
        )
        .unwrap();
    registry
}

struct WorkflowController {
    after_write: Control,
}

impl Controller for WorkflowController {
    fn next(&mut self, view: &RunView<'_>) -> Result<Control> {
        Ok(match view.last_completed {
            None => Control::Add(vec![Node {
                id: 1,
                operation: Operation::Read {
                    target: CellTarget::Pinned {
                        reference: CellRef { id: 1, revision: 1 },
                    },
                },
            }]),
            Some(1) => Control::Add(vec![Node {
                id: 2,
                operation: Operation::Apply {
                    operator: "double_plus_one".into(),
                    input: 1,
                },
            }]),
            Some(2) => Control::Add(vec![Node {
                id: 3,
                operation: Operation::Write {
                    cell_id: 1,
                    expected_revision: Some(1),
                    input: 2,
                },
            }]),
            Some(3) => match std::mem::replace(&mut self.after_write, Control::Halt) {
                Control::Add(nodes) => Control::Add(nodes),
                _ => Control::Add(vec![Node {
                    id: 4,
                    operation: Operation::Emit { input: 2 },
                }]),
            },
            Some(4) => Control::Halt,
            _ => return Err(Error::new("test_controller", "unexpected workflow state")),
        })
    }
}

fn limits(max_nodes: usize) -> RunLimits {
    RunLimits {
        max_nodes,
        max_graph_bytes: 32_768,
        max_scalar_ops: 100,
        max_payload_bytes: 1024,
        max_commit_validation_bytes: 1024,
        max_active_value_bytes: 1024,
        max_staged_bytes: 1024,
        max_trace_bytes: 32_768,
        max_wall_millis: 10_000,
    }
}

fn provenance() -> Provenance {
    Provenance::ScriptedFixture {
        description: "provider conformance workflow".into(),
    }
}

#[test]
fn independent_memory_provider_executes_and_commits_the_shared_workflow() {
    let provider = MemoryProvider::new(all_capabilities());
    let mut controller = WorkflowController {
        after_write: Control::Halt,
    };
    let registered = registry();
    let expected_parameters_hash = sha256(&serde_json::to_vec(&affine()).unwrap());
    let result = execute(
        &provider,
        &registered,
        &mut controller,
        provenance(),
        limits(4),
    )
    .unwrap();

    assert_eq!(result.values[&2], Value::Dense { data: vec![5.0] });
    assert_eq!(result.emissions, vec![4]);
    assert_eq!(result.values[&4], Value::Dense { data: vec![5.0] });
    assert_eq!(provider.current(), (2, Value::Dense { data: vec![5.0] }));
    assert_eq!(result.receipt.provider.name, "test-memory");
    assert!(result.receipt.provider.atomic_commit);
    assert!(result.receipt.provider.revision_checked);
    assert_eq!(result.receipt.commit.generation, 2);
    assert_eq!(
        result.receipt.commit.changed_cells,
        vec![CellRef { id: 1, revision: 2 }]
    );
    assert_eq!(result.receipt.commit.reads.payload_reads, 1);
    assert_eq!(
        result.receipt.commit.reads.payload_bytes,
        result.receipt.metrics.payload_bytes
    );
    assert_eq!(result.receipt.metrics.staged_bytes, 4);
    assert_eq!(
        result.receipt.trace[1].operator_sha256.as_deref(),
        Some(expected_parameters_hash.as_str())
    );
}

#[test]
fn provider_without_affine_refuses_before_invoking_the_operation() {
    let provider = MemoryProvider::new(vec![
        Capability::Read,
        Capability::Select,
        Capability::Write,
    ]);
    let mut controller = WorkflowController {
        after_write: Control::Halt,
    };
    let result = execute(
        &provider,
        &registry(),
        &mut controller,
        provenance(),
        limits(4),
    );

    let error = match result {
        Ok(_) => panic!("provider without affine capability should fail"),
        Err(error) => error,
    };
    assert_eq!(error.code, "unsupported_operation");
    assert_eq!(provider.affine_calls.get(), 0);
    assert_eq!(provider.current(), (1, Value::Dense { data: vec![2.0] }));
}

#[test]
fn node_budget_failure_after_staging_leaves_provider_state_unchanged() {
    let provider = MemoryProvider::new(all_capabilities());
    let mut controller = WorkflowController {
        after_write: Control::Add(vec![Node {
            id: 4,
            operation: Operation::Emit { input: 2 },
        }]),
    };
    let result = execute(
        &provider,
        &registry(),
        &mut controller,
        provenance(),
        limits(3),
    );

    let error = match result {
        Ok(_) => panic!("excess node should exceed the run budget"),
        Err(error) => error,
    };
    assert_eq!(error.code, "run_budget");
    assert_eq!(provider.current(), (1, Value::Dense { data: vec![2.0] }));
}

#[test]
fn memory_transaction_enforces_revision_staging_and_commit_conflicts() {
    let provider = MemoryProvider::new(all_capabilities());
    assert_eq!(
        provider
            .begin()
            .unwrap()
            .write(99, None, Value::Dense { data: vec![7.0] }, 1024)
            .unwrap_err()
            .code,
        "unsupported_operation"
    );
    let mut too_small = provider.begin().unwrap();
    assert_eq!(
        too_small
            .write(1, Some(1), Value::Dense { data: vec![5.0] }, 1)
            .unwrap_err()
            .code,
        "store_budget"
    );
    assert_eq!(too_small.staged_bytes(), 0);
    assert_eq!(
        too_small
            .write(1, Some(2), Value::Dense { data: vec![5.0] }, 1024)
            .unwrap_err()
            .code,
        "write_conflict"
    );

    let mut stale = provider.begin().unwrap();
    stale
        .write(1, Some(1), Value::Dense { data: vec![5.0] }, 1024)
        .unwrap();
    let mut winner = provider.begin().unwrap();
    winner
        .write(1, Some(1), Value::Dense { data: vec![7.0] }, 1024)
        .unwrap();
    winner.commit(1024).unwrap();
    assert_eq!(stale.commit(1024).unwrap_err().code, "write_conflict");
    assert_eq!(provider.current(), (2, Value::Dense { data: vec![7.0] }));
}
