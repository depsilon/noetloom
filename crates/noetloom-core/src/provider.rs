//! Physical execution is replaceable; controllers and operation semantics are independent.
//! Provider implementations are trusted code and must earn their stated guarantees in tests.
use serde::{Deserialize, Serialize};

use crate::operator::Affine;
use crate::store::{CommitReceipt, ReadAdmission, ReadMetrics, Store, Transaction};
use crate::value::{CellRef, Value};
use crate::{Error, Result};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Capability {
    Read,
    Select,
    Affine,
    Write,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ProviderDescriptor {
    pub name: String,
    pub version: String,
    pub representations: Vec<String>,
    pub capabilities: Vec<Capability>,
    pub atomic_commit: bool,
    pub revision_checked: bool,
    pub external_execution: bool,
}

/// Exact references and transaction-local writes are semantic requirements. On commit,
/// return a receipt or an explicit durability-uncertain error if visibility already changed.
pub trait StateTransaction {
    fn read_admission(&self, reference: CellRef) -> Result<ReadAdmission>;
    fn read(&mut self, reference: CellRef) -> Result<Value>;
    fn write(
        &mut self,
        id: u64,
        expected: Option<u64>,
        value: Value,
        max_staged_bytes: u64,
    ) -> Result<CellRef>;
    fn staged_bytes(&self) -> u64;
    fn read_metrics(&self) -> &ReadMetrics;
    fn commit(self, max_validation_bytes: u64) -> Result<CommitReceipt>;
}

/// The current operation vocabulary is deliberately small and versioned by the receipt.
/// It is not a complete semantic cognition interface or a fixed representation ontology.
pub trait ExecutionProvider {
    type Transaction<'a>: StateTransaction
    where
        Self: 'a;

    fn descriptor(&self) -> ProviderDescriptor;
    fn metadata_bytes_read(&self) -> u64;
    fn begin(&self) -> Result<Self::Transaction<'_>>;
    fn affine(&self, operator: &Affine, input: &Value) -> Result<Value>;
    /// Select the first maximum score; scores must be finite and match the choices.
    fn select(&self, scores: &Value, choices: &[CellRef]) -> Result<CellRef>;
}

impl StateTransaction for Transaction<'_> {
    fn read_admission(&self, reference: CellRef) -> Result<ReadAdmission> {
        self.read_admission(reference)
    }
    fn read(&mut self, reference: CellRef) -> Result<Value> {
        self.read(reference)
    }
    fn write(
        &mut self,
        id: u64,
        expected: Option<u64>,
        value: Value,
        max_staged_bytes: u64,
    ) -> Result<CellRef> {
        self.write(id, expected, value, max_staged_bytes)
    }
    fn staged_bytes(&self) -> u64 {
        self.staged_bytes()
    }
    fn read_metrics(&self) -> &ReadMetrics {
        self.read_metrics()
    }
    fn commit(self, max_validation_bytes: u64) -> Result<CommitReceipt> {
        self.commit_with_validation_limit(max_validation_bytes)
    }
}

impl ExecutionProvider for Store {
    type Transaction<'a> = Transaction<'a>;
    fn descriptor(&self) -> ProviderDescriptor {
        ProviderDescriptor {
            name: "noetloom-json-cpu".into(),
            version: env!("CARGO_PKG_VERSION").into(),
            representations: vec!["dense_f32".into(), "bytes".into(), "cell_references".into()],
            capabilities: vec![
                Capability::Read,
                Capability::Select,
                Capability::Affine,
                Capability::Write,
            ],
            atomic_commit: true,
            revision_checked: true,
            external_execution: false,
        }
    }
    fn metadata_bytes_read(&self) -> u64 {
        self.metadata_bytes_read
    }
    fn begin(&self) -> Result<Self::Transaction<'_>> {
        Ok(self.transaction())
    }
    fn affine(&self, operator: &Affine, input: &Value) -> Result<Value> {
        operator.apply(input)
    }
    fn select(&self, scores: &Value, choices: &[CellRef]) -> Result<CellRef> {
        select_first(scores, choices)
    }
}

pub(crate) fn select_first(scores: &Value, choices: &[CellRef]) -> Result<CellRef> {
    let Value::Dense { data } = scores else {
        return Err(Error::new(
            "invalid_input",
            "selection scores must be dense",
        ));
    };
    if choices.is_empty()
        || data.len() != choices.len()
        || data.iter().any(|score| !score.is_finite())
    {
        return Err(Error::new(
            "invalid_input",
            "selection needs matching, finite, nonempty scores and choices",
        ));
    }
    let mut selected = 0;
    for index in 1..data.len() {
        if data[index] > data[selected] {
            selected = index;
        }
    }
    choices[selected].validate()?;
    Ok(choices[selected])
}
