//! A controller proposes low-level work; only a successful halt commits state.
use std::collections::{BTreeMap, BTreeSet};
use std::time::Instant;

use serde::{Deserialize, Serialize};

use crate::operator::Affine;
use crate::provider::{Capability, ExecutionProvider, ProviderDescriptor, StateTransaction};
use crate::store::{CommitReceipt, sha256};
use crate::value::{CellRef, Value};
use crate::{Error, Result};

pub type NodeId = u64;

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Provenance {
    ScriptedFixture {
        description: String,
    },
    /// A label for supplied parameters; the runtime does not certify training claims.
    Artifact {
        sha256: String,
    },
}

struct RegisteredOperator {
    affine: Affine,
    identity: OperatorIdentity,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OperatorIdentity {
    pub parameters_sha256: String,
    pub provenance: Provenance,
}

#[derive(Default)]
pub struct Registry {
    operators: BTreeMap<String, RegisteredOperator>,
}

impl Registry {
    pub fn register(&mut self, name: &str, affine: Affine, provenance: Provenance) -> Result<()> {
        if name.is_empty()
            || name.len() > 128
            || self.operators.contains_key(name)
            || self.operators.len() >= 64
        {
            return Err(Error::new(
                "invalid_operator",
                "operator name is invalid, duplicated, or registry is full",
            ));
        }
        affine.validate()?;
        match &provenance {
            Provenance::ScriptedFixture { description }
                if description.is_empty() || description.len() > 1024 =>
            {
                return Err(Error::new(
                    "invalid_operator",
                    "fixture description must contain 1..1024 bytes",
                ));
            }
            Provenance::Artifact { sha256 }
                if sha256.len() != 64
                    || !sha256
                        .bytes()
                        .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)) =>
            {
                return Err(Error::new(
                    "invalid_operator",
                    "artifact identity must be a SHA-256 digest",
                ));
            }
            _ => (),
        }
        let parameters_sha256 = sha256(&serde_json::to_vec(&affine)?);
        self.operators.insert(
            name.into(),
            RegisteredOperator {
                affine,
                identity: OperatorIdentity {
                    parameters_sha256,
                    provenance,
                },
            },
        );
        Ok(())
    }

    pub fn identities(&self) -> BTreeMap<String, OperatorIdentity> {
        self.operators
            .iter()
            .map(|(name, operator)| (name.clone(), operator.identity.clone()))
            .collect()
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum CellTarget {
    Pinned { reference: CellRef },
    FromNode { node: NodeId },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Operation {
    Read {
        target: CellTarget,
    },
    Select {
        scores: NodeId,
        choices: Vec<CellRef>,
    },
    Apply {
        operator: String,
        input: NodeId,
    },
    Write {
        cell_id: u64,
        expected_revision: Option<u64>,
        input: NodeId,
    },
    Emit {
        input: NodeId,
    },
}

impl Operation {
    fn capability(&self) -> Option<Capability> {
        match self {
            Self::Read { .. } => Some(Capability::Read),
            Self::Select { .. } => Some(Capability::Select),
            Self::Apply { .. } => Some(Capability::Affine),
            Self::Write { .. } => Some(Capability::Write),
            Self::Emit { .. } => None,
        }
    }
    fn inputs(&self) -> Vec<NodeId> {
        match self {
            Self::Read {
                target: CellTarget::Pinned { .. },
            } => vec![],
            Self::Read {
                target: CellTarget::FromNode { node },
            } => vec![*node],
            Self::Select { scores, .. } => vec![*scores],
            Self::Apply { input, .. } | Self::Write { input, .. } | Self::Emit { input } => {
                vec![*input]
            }
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Node {
    pub id: NodeId,
    pub operation: Operation,
}

pub enum Control {
    Add(Vec<Node>),
    Continue,
    Halt,
}

pub struct RunView<'a> {
    pub values: &'a BTreeMap<NodeId, Value>,
    pub last_completed: Option<NodeId>,
    pub pending_nodes: usize,
}

/// Implementations are trusted local code. Deadlines are cooperative, not preemption.
pub trait Controller {
    fn next(&mut self, view: &RunView<'_>) -> Result<Control>;
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RunLimits {
    pub max_nodes: usize,
    pub max_graph_bytes: u64,
    pub max_scalar_ops: u64,
    pub max_payload_bytes: u64,
    pub max_commit_validation_bytes: u64,
    pub max_active_value_bytes: u64,
    pub max_staged_bytes: u64,
    pub max_trace_bytes: u64,
    pub max_wall_millis: u64,
}

impl Default for RunLimits {
    fn default() -> Self {
        Self {
            max_nodes: 256,
            max_graph_bytes: 256 << 10,
            max_scalar_ops: 1_000_000,
            max_payload_bytes: 1 << 20,
            max_commit_validation_bytes: 1 << 20,
            max_active_value_bytes: 1 << 20,
            max_staged_bytes: 1 << 20,
            max_trace_bytes: 256 << 10,
            max_wall_millis: 10_000,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct RunMetrics {
    pub submitted_nodes: usize,
    pub submitted_graph_bytes: u64,
    pub executed_nodes: usize,
    pub scalar_ops: u64,
    pub payload_reads: u64,
    pub payload_bytes: u64,
    pub active_value_bytes: u64,
    pub staged_bytes: u64,
    pub trace_bytes: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct TraceEntry {
    pub node: NodeId,
    pub operation: String,
    pub inputs: Vec<NodeId>,
    pub cell: Option<CellRef>,
    pub operator_sha256: Option<String>,
    pub output_bytes: u64,
    pub scalar_ops: u64,
    pub payload_bytes: u64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct RunReceipt {
    pub schema: String,
    pub provider: ProviderDescriptor,
    pub controller_provenance: Provenance,
    pub operators: BTreeMap<String, OperatorIdentity>,
    pub limits: RunLimits,
    pub metrics: RunMetrics,
    pub metadata_bytes_read: u64,
    pub trace: Vec<TraceEntry>,
    pub commit: CommitReceipt,
    pub elapsed_micros: u128,
}

pub struct RunResult {
    pub values: BTreeMap<NodeId, Value>,
    /// References into values; emissions do not make another payload copy.
    pub emissions: Vec<NodeId>,
    pub receipt: RunReceipt,
}

fn add_budget(current: u64, extra: u64, limit: u64, label: &str) -> Result<u64> {
    current
        .checked_add(extra)
        .filter(|total| *total <= limit)
        .ok_or_else(|| Error::new("run_budget", format!("{label} exceeds run budget")))
}

fn check_time(start: Instant, limits: RunLimits) -> Result<()> {
    if start.elapsed().as_millis() >= limits.max_wall_millis as u128 {
        return Err(Error::new(
            "run_budget",
            "cooperative wall-time deadline exceeded",
        ));
    }
    Ok(())
}

/// Values remain resident until completion; their aggregate logical bytes are bounded.
/// Parameter/index memory and serialization overhead have separate finite structural caps.
pub fn execute(
    provider: &impl ExecutionProvider,
    registry: &Registry,
    controller: &mut impl Controller,
    controller_provenance: Provenance,
    limits: RunLimits,
) -> Result<RunResult> {
    if limits.max_nodes == 0 || limits.max_nodes > 65_536 || limits.max_wall_millis == 0 {
        return Err(Error::new(
            "invalid_limits",
            "execution requires 1..65536 nodes and a positive deadline",
        ));
    }
    let start = Instant::now();
    let descriptor = provider.descriptor();
    if !descriptor.atomic_commit || !descriptor.revision_checked || descriptor.external_execution {
        return Err(Error::new(
            "unsupported_provider",
            "this executor requires local revision-checked atomic transactions",
        ));
    }
    let mut transaction = provider.begin()?;
    let mut submitted = BTreeSet::<NodeId>::new();
    let mut values = BTreeMap::new();
    let mut pending = BTreeMap::<NodeId, Node>::new();
    let mut emissions = Vec::new();
    let mut trace = Vec::new();
    let mut metrics = RunMetrics {
        trace_bytes: 2,
        ..RunMetrics::default()
    };
    let mut last_completed = None;
    loop {
        check_time(start, limits)?;
        let decision = controller.next(&RunView {
            values: &values,
            last_completed,
            pending_nodes: pending.len(),
        })?;
        check_time(start, limits)?;
        match decision {
            Control::Halt => {
                if !pending.is_empty() {
                    return Err(Error::new(
                        "invalid_graph",
                        "controller halted with unfinished work",
                    ));
                }
                if metrics.trace_bytes > limits.max_trace_bytes {
                    return Err(Error::new("run_budget", "trace exceeds budget"));
                }
                metrics.staged_bytes = transaction.staged_bytes();
                let commit = transaction.commit(limits.max_commit_validation_bytes)?;
                let receipt = RunReceipt {
                    schema: "noetloom.execution.v1".into(),
                    provider: descriptor,
                    controller_provenance,
                    operators: registry.identities(),
                    limits,
                    metrics,
                    metadata_bytes_read: provider.metadata_bytes_read(),
                    trace,
                    commit,
                    elapsed_micros: start.elapsed().as_micros(),
                };
                return Ok(RunResult {
                    values,
                    emissions,
                    receipt,
                });
            }
            Control::Continue => (),
            Control::Add(nodes) => {
                if submitted
                    .len()
                    .checked_add(nodes.len())
                    .is_none_or(|total| total > limits.max_nodes)
                {
                    return Err(Error::new("run_budget", "submitted node budget exceeded"));
                }
                for node in nodes {
                    if submitted.contains(&node.id)
                        || node
                            .operation
                            .inputs()
                            .iter()
                            .any(|id| !submitted.contains(id))
                    {
                        return Err(Error::new(
                            "invalid_graph",
                            "node IDs must be unique and inputs must already be submitted",
                        ));
                    }
                    if node
                        .operation
                        .capability()
                        .is_some_and(|capability| !descriptor.capabilities.contains(&capability))
                    {
                        return Err(Error::new(
                            "unsupported_operation",
                            "selected provider does not support this operation; no fallback is enabled",
                        ));
                    }
                    match &node.operation {
                        Operation::Select { choices, .. } => {
                            if choices.is_empty() || choices.len() > 4096 {
                                return Err(Error::new(
                                    "invalid_graph",
                                    "selection needs 1..4096 choices",
                                ));
                            }
                            for reference in choices {
                                reference.validate()?;
                            }
                        }
                        Operation::Apply { operator, .. }
                            if !registry.operators.contains_key(operator) =>
                        {
                            return Err(Error::new("invalid_graph", "unknown operator"));
                        }
                        Operation::Read {
                            target: CellTarget::Pinned { reference },
                        } => reference.validate()?,
                        _ => (),
                    }
                    let node_bytes = serde_json::to_vec(&node)?.len() as u64;
                    metrics.submitted_graph_bytes = add_budget(
                        metrics.submitted_graph_bytes,
                        node_bytes,
                        limits.max_graph_bytes,
                        "submitted graph",
                    )?;
                    submitted.insert(node.id);
                    pending.insert(node.id, node);
                }
                metrics.submitted_nodes = submitted.len();
            }
        }
        let id = pending
            .iter()
            .find(|(_, node)| {
                node.operation
                    .inputs()
                    .iter()
                    .all(|input| values.contains_key(input))
            })
            .map(|(id, _)| *id)
            .ok_or_else(|| Error::new("invalid_graph", "controller made no executable progress"))?;
        let node = pending.remove(&id).expect("selected pending node");
        // Reserve a conservative upper bound before work; actual trace bytes are recorded below.
        let trace_reservation = serde_json::to_vec(&node)?.len() as u64 + 512;
        add_budget(
            metrics.trace_bytes,
            trace_reservation,
            limits.max_trace_bytes,
            "trace reservation",
        )?;
        check_time(start, limits)?;
        let mut entry = TraceEntry {
            node: id,
            operation: String::new(),
            inputs: node.operation.inputs(),
            cell: None,
            operator_sha256: None,
            output_bytes: 0,
            scalar_ops: 0,
            payload_bytes: 0,
        };
        let value = match &node.operation {
            Operation::Read { target } => {
                entry.operation = "read".into();
                let reference = match target {
                    CellTarget::Pinned { reference } => *reference,
                    CellTarget::FromNode { node } => match &values[node] {
                        Value::Refs { data } if data.len() == 1 => data[0],
                        _ => {
                            return Err(Error::new(
                                "invalid_input",
                                "read requires exactly one cell reference",
                            ));
                        }
                    },
                };
                let admission = transaction.read_admission(reference)?;
                add_budget(
                    metrics.payload_bytes,
                    admission.payload_bytes,
                    limits.max_payload_bytes,
                    "payload I/O",
                )?;
                add_budget(
                    metrics.active_value_bytes,
                    admission.value_bytes,
                    limits.max_active_value_bytes,
                    "active values",
                )?;
                entry.cell = Some(reference);
                entry.payload_bytes = admission.payload_bytes;
                transaction.read(reference)?
            }
            Operation::Select { scores, choices } => {
                entry.operation = "select".into();
                let Value::Dense { data } = &values[scores] else {
                    return Err(Error::new(
                        "invalid_input",
                        "selection scores must be dense",
                    ));
                };
                if data.len() != choices.len() {
                    return Err(Error::new(
                        "invalid_input",
                        "score and choice counts differ",
                    ));
                }
                entry.scalar_ops = choices.len().saturating_sub(1) as u64;
                add_budget(
                    metrics.scalar_ops,
                    entry.scalar_ops,
                    limits.max_scalar_ops,
                    "scalar work",
                )?;
                add_budget(
                    metrics.active_value_bytes,
                    16,
                    limits.max_active_value_bytes,
                    "active values",
                )?;
                let selected = provider.select(&values[scores], choices)?;
                entry.cell = Some(selected);
                Value::Refs {
                    data: vec![selected],
                }
            }
            Operation::Apply { operator, input } => {
                entry.operation = "apply".into();
                let operator = &registry.operators[operator];
                entry.scalar_ops = operator.affine.scalar_ops()?;
                entry.operator_sha256 = Some(operator.identity.parameters_sha256.clone());
                add_budget(
                    metrics.scalar_ops,
                    entry.scalar_ops,
                    limits.max_scalar_ops,
                    "scalar work",
                )?;
                add_budget(
                    metrics.active_value_bytes,
                    operator.affine.output_dim as u64 * 4,
                    limits.max_active_value_bytes,
                    "active values",
                )?;
                provider.affine(&operator.affine, &values[input])?
            }
            Operation::Write {
                cell_id,
                expected_revision,
                input,
            } => {
                entry.operation = "write".into();
                add_budget(
                    metrics.active_value_bytes,
                    16,
                    limits.max_active_value_bytes,
                    "active values",
                )?;
                let reference = transaction.write(
                    *cell_id,
                    *expected_revision,
                    values[input].clone(),
                    limits.max_staged_bytes,
                )?;
                entry.cell = Some(reference);
                Value::Refs {
                    data: vec![reference],
                }
            }
            Operation::Emit { input } => {
                entry.operation = "emit".into();
                add_budget(
                    metrics.active_value_bytes,
                    values[input].logical_bytes()?,
                    limits.max_active_value_bytes,
                    "active values",
                )?;
                emissions.push(id);
                values[input].clone()
            }
        };
        entry.output_bytes = value.logical_bytes()?;
        metrics.active_value_bytes = add_budget(
            metrics.active_value_bytes,
            entry.output_bytes,
            limits.max_active_value_bytes,
            "active values",
        )?;
        metrics.scalar_ops += entry.scalar_ops;
        metrics.payload_reads = transaction.read_metrics().payload_reads;
        metrics.payload_bytes = transaction.read_metrics().payload_bytes;
        let entry_bytes = serde_json::to_vec(&entry)?.len() as u64 + u64::from(!trace.is_empty());
        metrics.trace_bytes = add_budget(
            metrics.trace_bytes,
            entry_bytes,
            limits.max_trace_bytes,
            "trace",
        )?;
        trace.push(entry);
        values.insert(id, value);
        metrics.executed_nodes += 1;
        last_completed = Some(id);
        check_time(start, limits)?;
    }
}
