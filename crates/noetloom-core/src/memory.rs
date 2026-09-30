//! Bounded resident provider. Snapshot pinning clones references, not payloads.
use std::cell::RefCell;
use std::collections::BTreeMap;
use std::rc::Rc;

use crate::operator::Affine;
use crate::provider::{Capability, ExecutionProvider, ProviderDescriptor, StateTransaction};
use crate::store::{CommitReceipt, ReadAdmission, ReadMetrics};
use crate::value::{CellRef, Value};
use crate::{Error, Result};

#[derive(Clone)]
struct Cell {
    revision: u64,
    value: Rc<Value>,
}

#[derive(Clone, Default)]
struct Snapshot {
    generation: u64,
    cells: BTreeMap<u64, Cell>,
    bytes: u64,
}

pub struct MemoryStore {
    snapshot: RefCell<Rc<Snapshot>>,
    max_cells: usize,
    max_bytes: u64,
}

impl MemoryStore {
    pub fn new(max_cells: usize, max_bytes: u64) -> Result<Self> {
        if max_cells == 0 || max_cells > 256 || max_bytes == 0 || max_bytes > 1024 * 1024 {
            return Err(Error::new("store_budget", "invalid resident store limits"));
        }
        Ok(Self {
            snapshot: RefCell::new(Rc::new(Snapshot::default())),
            max_cells,
            max_bytes,
        })
    }
}

pub struct MemoryTransaction<'a> {
    store: &'a MemoryStore,
    pinned: Rc<Snapshot>,
    staged: BTreeMap<u64, Cell>,
    staged_bytes: u64,
    reads: ReadMetrics,
}

impl MemoryTransaction<'_> {
    fn cell(&self, reference: CellRef) -> Result<&Cell> {
        reference.validate()?;
        let cell = self
            .staged
            .get(&reference.id)
            .or_else(|| self.pinned.cells.get(&reference.id));
        match cell {
            Some(cell) if cell.revision == reference.revision => Ok(cell),
            _ => Err(Error::new(
                "stale_reference",
                "resident cell revision is absent",
            )),
        }
    }
}

impl StateTransaction for MemoryTransaction<'_> {
    fn read_admission(&self, reference: CellRef) -> Result<ReadAdmission> {
        let bytes = self.cell(reference)?.value.logical_bytes()?;
        Ok(ReadAdmission {
            payload_bytes: if self.staged.contains_key(&reference.id) {
                0
            } else {
                bytes
            },
            value_bytes: bytes,
        })
    }

    fn read(&mut self, reference: CellRef) -> Result<Value> {
        let admission = self.read_admission(reference)?;
        let value = self.cell(reference)?.value.as_ref().clone();
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
        value.validate(self.store.max_bytes)?;
        let old = self.staged.get(&id).or_else(|| self.pinned.cells.get(&id));
        if old.map(|cell| cell.revision) != expected {
            return Err(Error::new(
                "write_conflict",
                "resident revision differs from expectation",
            ));
        }
        let revision = expected
            .unwrap_or(0)
            .checked_add(1)
            .ok_or_else(|| Error::new("write_conflict", "revision exhausted"))?;
        let old_staged = self
            .staged
            .get(&id)
            .map(|cell| cell.value.logical_bytes())
            .transpose()?
            .unwrap_or(0);
        let staged_bytes = self.staged_bytes - old_staged + value.logical_bytes()?;
        let new_cells = self
            .staged
            .keys()
            .filter(|key| !self.pinned.cells.contains_key(key))
            .count();
        let count = self.pinned.cells.len() + new_cells + usize::from(old.is_none());
        let replaced: u64 = self
            .staged
            .keys()
            .filter_map(|key| self.pinned.cells.get(key))
            .map(|cell| cell.value.logical_bytes())
            .collect::<Result<Vec<_>>>()?
            .iter()
            .sum();
        let extra_replaced = if self.staged.contains_key(&id) {
            0
        } else {
            self.pinned
                .cells
                .get(&id)
                .map(|cell| cell.value.logical_bytes())
                .transpose()?
                .unwrap_or(0)
        };
        if staged_bytes > max_staged_bytes
            || count > self.store.max_cells
            || self.pinned.bytes - replaced - extra_replaced + staged_bytes > self.store.max_bytes
        {
            return Err(Error::new(
                "store_budget",
                "resident transaction exceeds admission",
            ));
        }
        self.staged.insert(
            id,
            Cell {
                revision,
                value: Rc::new(value),
            },
        );
        self.staged_bytes = staged_bytes;
        Ok(CellRef { id, revision })
    }

    fn staged_bytes(&self) -> u64 {
        self.staged_bytes
    }
    fn read_metrics(&self) -> &ReadMetrics {
        &self.reads
    }

    fn commit(self, _max_validation_bytes: u64) -> Result<CommitReceipt> {
        let mut live = self.store.snapshot.borrow_mut();
        if live.generation != self.pinned.generation {
            return Err(Error::new("write_conflict", "resident snapshot advanced"));
        }
        let before = format!("memory-generation-{}", live.generation);
        let changed_cells: Vec<_> = self
            .staged
            .iter()
            .map(|(id, cell)| CellRef {
                id: *id,
                revision: cell.revision,
            })
            .collect();
        if !self.staged.is_empty() {
            let generation = live
                .generation
                .checked_add(1)
                .ok_or_else(|| Error::new("write_conflict", "generation exhausted"))?;
            let mut next = live.as_ref().clone(); // Rc<Value> clones do not activate payloads.
            for (id, cell) in self.staged {
                if let Some(old) = next.cells.insert(id, cell.clone()) {
                    next.bytes -= old.value.logical_bytes()?;
                }
                next.bytes += cell.value.logical_bytes()?;
            }
            next.generation = generation;
            *live = Rc::new(next);
        }
        Ok(CommitReceipt {
            before,
            after: format!("memory-generation-{}", live.generation),
            generation: live.generation,
            changed_cells,
            new_file_bytes: 0,
            validation_reads: 0,
            validation_bytes: 0,
            reads: self.reads,
        })
    }
}

impl ExecutionProvider for MemoryStore {
    type Transaction<'a> = MemoryTransaction<'a>;
    fn descriptor(&self) -> ProviderDescriptor {
        ProviderDescriptor {
            name: "noetloom-resident-cpu".into(),
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
        0
    }
    fn begin(&self) -> Result<Self::Transaction<'_>> {
        Ok(MemoryTransaction {
            store: self,
            pinned: self.snapshot.borrow().clone(),
            staged: BTreeMap::new(),
            staged_bytes: 0,
            reads: ReadMetrics::default(),
        })
    }
    fn affine(&self, operator: &Affine, input: &Value) -> Result<Value> {
        operator.apply(input)
    }
    fn select(&self, scores: &Value, choices: &[CellRef]) -> Result<CellRef> {
        crate::provider::select_first(scores, choices)
    }
}
