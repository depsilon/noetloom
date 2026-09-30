//! A restartable infrastructure fixture, deliberately not a learned controller.
use std::path::Path;

use noetloom_core::engine::{
    CellTarget, Control, Controller, Node, Operation, Provenance, Registry, RunLimits, RunView,
    execute,
};
use noetloom_core::operator::{Activation, Affine};
use noetloom_core::store::{Store, StoreLimits};
use noetloom_core::value::{CellRef, Value};
use noetloom_core::{Error, Result};

fn reference(id: u64, revision: u64) -> CellRef {
    CellRef { id, revision }
}
fn fixture() -> Provenance {
    Provenance::ScriptedFixture { description: "Select the higher supplied score, increment until three, then persist; hand-authored weights and control.".into() }
}

struct FixtureController {
    next: u64,
    selected: Option<CellRef>,
    final_value: Option<u64>,
    written: bool,
    emitted: bool,
}
impl Controller for FixtureController {
    fn next(&mut self, view: &RunView<'_>) -> Result<Control> {
        if self.emitted {
            return Ok(Control::Halt);
        }
        let operation = match view.last_completed {
            None => Operation::Read {
                target: CellTarget::Pinned {
                    reference: reference(42, 1),
                },
            },
            Some(1) => Operation::Select {
                scores: 1,
                choices: vec![reference(0, 1), reference(1, 1)],
            },
            Some(2) => {
                let Value::Refs { data } = &view.values[&2] else {
                    return Err(Error::new(
                        "fixture_failed",
                        "selection did not produce references",
                    ));
                };
                self.selected = Some(data[0]);
                Operation::Read {
                    target: CellTarget::FromNode { node: 2 },
                }
            }
            Some(_) if self.written => {
                self.emitted = true;
                Operation::Emit {
                    input: self.final_value.unwrap(),
                }
            }
            Some(last) => {
                let Value::Dense { data } = &view.values[&last] else {
                    return Err(Error::new("fixture_failed", "expected a dense scalar"));
                };
                if data[0] < 3.0 {
                    Operation::Apply {
                        operator: "increment".into(),
                        input: last,
                    }
                } else {
                    self.final_value = Some(last);
                    self.written = true;
                    let reference = self.selected.unwrap();
                    Operation::Write {
                        cell_id: reference.id,
                        expected_revision: Some(reference.revision),
                        input: last,
                    }
                }
            }
        };
        let id = self.next;
        self.next += 1;
        Ok(Control::Add(vec![Node { id, operation }]))
    }
}

fn build_identity() -> serde_json::Value {
    serde_json::from_str(include_str!(concat!(
        env!("OUT_DIR"),
        "/build-identity.json"
    )))
    .expect("compiled build identity")
}

fn run(path: &Path) -> Result<serde_json::Value> {
    let store = Store::create(path, StoreLimits::default())?;
    let mut transaction = store.transaction();
    transaction.write(0, None, Value::Dense { data: vec![0.0] }, 1 << 20)?;
    transaction.write(1, None, Value::Dense { data: vec![1.0] }, 1 << 20)?;
    transaction.write(
        42,
        None,
        Value::Dense {
            data: vec![0.1, 0.9],
        },
        1 << 20,
    )?;
    transaction.write(
        999,
        None,
        Value::Bytes {
            data: vec![17; 65_536],
        },
        1 << 20,
    )?;
    let initialization = transaction.commit()?;
    let store = Store::open(path, StoreLimits::default())?;
    let mut registry = Registry::default();
    registry.register(
        "increment",
        Affine {
            input_dim: 1,
            output_dim: 1,
            weights: vec![1.0],
            bias: vec![1.0],
            activation: Activation::Identity,
        },
        fixture(),
    )?;
    let mut controller = FixtureController {
        next: 1,
        selected: None,
        final_value: None,
        written: false,
        emitted: false,
    };
    let result = execute(
        &store,
        &registry,
        &mut controller,
        fixture(),
        RunLimits::default(),
    )?;
    if result.values[&result.emissions[0]] != (Value::Dense { data: vec![3.0] })
        || result.receipt.metrics.payload_reads != 2
        || result.receipt.commit.changed_cells != vec![reference(1, 2)]
    {
        return Err(Error::new(
            "fixture_failed",
            "unexpected result or activation behavior",
        ));
    }
    Ok(serde_json::json!({
        "schema": "noetloom.foundation_fixture.v1", "training_performed": false,
        "claim_boundary": "Persistent-state and dynamic-execution infrastructure only; no learned cognition or provider superiority.",
        "build": build_identity(), "initialization": initialization,
        "execution": result.receipt, "emitted_value": result.values[&result.emissions[0]],
        "inactive_cell": reference(999, 1), "inactive_logical_bytes": 65_536,
    }))
}

fn verify(path: &Path) -> Result<serde_json::Value> {
    let store = Store::open(path, StoreLimits::default())?;
    if store.cell_ref(1) != Some(reference(1, 2))
        || store.cell_ref(0) != Some(reference(0, 1))
        || store.cell_ref(42) != Some(reference(42, 1))
        || store.cell_ref(999) != Some(reference(999, 1))
    {
        return Err(Error::new("fixture_failed", "restart revisions differ"));
    }
    let mut transaction = store.transaction();
    let value = transaction.read(reference(1, 2))?;
    if value != (Value::Dense { data: vec![3.0] }) {
        return Err(Error::new("fixture_failed", "restart value differs"));
    }
    Ok(
        serde_json::json!({"schema": "noetloom.foundation_restart.v1", "status": "passed", "build": build_identity(), "snapshot": store.snapshot_id(), "value": value, "reads": transaction.read_metrics()}),
    )
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let result = if args.len() == 3 {
        match args[1].as_str() {
            "run" => run(Path::new(&args[2])),
            "verify" => verify(Path::new(&args[2])),
            _ => Err(Error::new(
                "usage",
                "foundation {run|verify} NEW_OR_EXISTING_STORE",
            )),
        }
    } else {
        Err(Error::new(
            "usage",
            "foundation {run|verify} NEW_OR_EXISTING_STORE",
        ))
    };
    match result {
        Ok(value) => println!("{}", serde_json::to_string(&value).unwrap()),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    }
}
