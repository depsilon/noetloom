//! EXP-0002 inference. Fixed experimental scaffold, not a general cognitive architecture.
use serde::{Deserialize, Serialize};
use std::time::Instant;

use crate::operator::{Activation, Affine};
use crate::provider::{Capability, ExecutionProvider, StateTransaction};
use crate::value::{CellRef, Value};
use crate::{Error, Result};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Arm {
    Selective,
    Dense,
    FrozenRouting,
    NoHistory,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Parameters {
    pub schema_version: String,
    pub arm: Arm,
    pub seed: u64,
    pub step: u64,
    pub query: Affine,
    pub key: Affine,
    pub encoder: Affine,
    pub decoder: Affine,
    pub age_coefficient: f32,
    pub null_score: f32,
    pub null_payload: Vec<f32>,
}

impl Parameters {
    pub fn validate(&self) -> Result<()> {
        if self.schema_version != "noetloom.cell_parameters.v1" || self.step > 256 {
            return Err(Error::new(
                "invalid_parameters",
                "unsupported learned artifact version or step",
            ));
        }
        for (matrix, input, output, activation) in [
            (&self.query, 16, 8, Activation::Identity),
            (&self.key, 16, 8, Activation::Identity),
            (&self.encoder, 5, 8, Activation::Tanh),
            (&self.decoder, 8, 5, Activation::Identity),
        ] {
            matrix.validate()?;
            if matrix.input_dim != input
                || matrix.output_dim != output
                || matrix.activation != activation
            {
                return Err(Error::new(
                    "invalid_parameters",
                    "parameter shape or activation differs from protocol",
                ));
            }
        }
        if self
            .query
            .bias
            .iter()
            .chain(self.key.bias.iter())
            .any(|value| *value != 0.0)
            || self.null_payload.len() != 8
            || self.null_payload.iter().any(|value| !value.is_finite())
            || !self.age_coefficient.is_finite()
            || !self.null_score.is_finite()
        {
            return Err(Error::new(
                "invalid_parameters",
                "invalid bias, null payload, or routing coefficient",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
pub enum Observation {
    Write { key: Vec<f32>, value: usize },
    Delete { key: Vec<f32> },
    Query { key: Vec<f32>, query_id: usize },
}

impl Observation {
    pub fn validate(&self) -> Result<()> {
        let key = match self {
            Self::Write { key, .. } | Self::Delete { key } | Self::Query { key, .. } => key,
        };
        if key.len() != 16 || key.iter().any(|x| *x != -1.0 && *x != 1.0) {
            return Err(Error::new(
                "invalid_observation",
                "keys must contain sixteen signed bits",
            ));
        }
        match self {
            Self::Write { value, .. } if *value >= 4 => Err(Error::new(
                "invalid_observation",
                "value class out of range",
            )),
            Self::Query { query_id, .. } if *query_id >= 8 => Err(Error::new(
                "invalid_observation",
                "query identity out of range",
            )),
            _ => Ok(()),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Episode {
    pub id: String,
    pub observations: Vec<Observation>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Descriptor {
    pub reference: CellRef,
    pub key: Vec<f32>,
    pub written_at: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct State {
    pub null_reference: CellRef,
    pub cells: Vec<Option<Descriptor>>,
    pub writes: u64,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Metrics {
    pub writes: u64,
    pub queries: u64,
    pub nominal_scalar_ops: u64,
    pub descriptor_read_bytes: u64,
    pub validation_descriptor_bytes: u64,
    pub payload_reads: u64,
    pub payload_read_bytes: u64,
    pub payload_write_bytes: u64,
    pub commit_validation_bytes: u64,
    pub peak_live_payload_bytes: u64,
    pub peak_descriptor_bytes: u64,
    pub peak_staged_bytes: u64,
    pub elapsed_ns: u128,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Prediction {
    pub query_id: usize,
    pub logits: Vec<f32>,
    pub prediction: usize,
    pub selected: Option<CellRef>,
}

fn dense(value: Value) -> Result<Vec<f32>> {
    match value {
        Value::Dense { data } => Ok(data),
        _ => Err(Error::new(
            "invalid_representation",
            "learned probe needs dense vectors",
        )),
    }
}

fn apply<P: ExecutionProvider>(
    provider: &P,
    matrix: &Affine,
    input: &[f32],
    metrics: &mut Metrics,
) -> Result<Vec<f32>> {
    let result = dense(provider.affine(
        matrix,
        &Value::Dense {
            data: input.to_vec(),
        },
    )?)?;
    metrics.nominal_scalar_ops += matrix.scalar_ops()?;
    Ok(result)
}

impl State {
    pub fn initialize<P: ExecutionProvider>(provider: &P, parameters: &Parameters) -> Result<Self> {
        parameters.validate()?;
        let descriptor = provider.descriptor();
        if ![
            Capability::Read,
            Capability::Select,
            Capability::Affine,
            Capability::Write,
        ]
        .iter()
        .all(|capability| descriptor.capabilities.contains(capability))
            || !descriptor.atomic_commit
            || !descriptor.revision_checked
        {
            return Err(Error::new(
                "unsupported_provider",
                "learning requires complete revisioned execution",
            ));
        }
        let mut transaction = provider.begin()?;
        let null_reference = transaction.write(
            0,
            None,
            Value::Dense {
                data: parameters.null_payload.clone(),
            },
            4096,
        )?;
        transaction.commit(1024 * 1024)?;
        Ok(Self {
            null_reference,
            cells: vec![None; 32],
            writes: 0,
        })
    }

    pub fn validate(&self) -> Result<()> {
        self.null_reference.validate()?;
        if self.null_reference.id != 0
            || self.null_reference.revision != 1
            || self.cells.len() != 32
            || self.writes > 128
        {
            return Err(Error::new(
                "invalid_state",
                "invalid learned-state checkpoint",
            ));
        }
        for (slot, cell) in self.cells.iter().enumerate() {
            if let Some(cell) = cell {
                cell.reference.validate()?;
                if cell.reference.id != slot as u64 + 1
                    || cell.key.len() != 8
                    || cell.key.iter().any(|value| !value.is_finite())
                    || cell.written_at == 0
                    || cell.written_at > self.writes
                {
                    return Err(Error::new("invalid_state", "invalid learned descriptor"));
                }
            }
        }
        Ok(())
    }

    pub fn step<P: ExecutionProvider>(
        &mut self,
        provider: &P,
        parameters: &Parameters,
        observation: &Observation,
        metrics: &mut Metrics,
    ) -> Result<Option<Prediction>> {
        let start = Instant::now();
        observation.validate()?;
        self.validate()?;
        metrics.validation_descriptor_bytes += self.cells.iter().flatten().count() as u64 * 56;
        let prediction = match observation {
            Observation::Write { key, value } => {
                self.write(provider, parameters, key, *value, metrics)?;
                None
            }
            Observation::Delete { key } => {
                self.write(provider, parameters, key, 4, metrics)?;
                None
            }
            Observation::Query { key, query_id } => {
                Some(self.query(provider, parameters, key, *query_id, metrics)?)
            }
        };
        metrics.elapsed_ns += start.elapsed().as_nanos();
        Ok(prediction)
    }

    fn write<P: ExecutionProvider>(
        &mut self,
        provider: &P,
        p: &Parameters,
        key: &[f32],
        value: usize,
        metrics: &mut Metrics,
    ) -> Result<()> {
        if self.writes >= 128 {
            return Err(Error::new("run_budget", "episode exceeds 128 writes"));
        }
        let mut input = vec![0.0; 5];
        input[value] = 1.0;
        let descriptor = apply(provider, &p.key, key, metrics)?;
        let payload = apply(provider, &p.encoder, &input, metrics)?;
        let slot = self.writes as usize % 32;
        let expected = self.cells[slot]
            .as_ref()
            .map(|cell| cell.reference.revision);
        let mut transaction = provider.begin()?;
        let reference = transaction.write(
            slot as u64 + 1,
            expected,
            Value::Dense { data: payload },
            4096,
        )?;
        metrics.peak_staged_bytes = metrics.peak_staged_bytes.max(transaction.staged_bytes());
        let receipt = transaction.commit(1024 * 1024)?;
        metrics.commit_validation_bytes += receipt.validation_bytes;
        self.writes += 1;
        self.cells[slot] = Some(Descriptor {
            reference,
            key: descriptor,
            written_at: self.writes,
        });
        metrics.writes += 1;
        metrics.payload_write_bytes += 32;
        let count = self.cells.iter().flatten().count() as u64;
        metrics.peak_live_payload_bytes = metrics.peak_live_payload_bytes.max((count + 1) * 32);
        // Logical descriptor: eight f32 coordinates, reference id/revision, write counter.
        metrics.peak_descriptor_bytes = metrics.peak_descriptor_bytes.max(count * 56);
        Ok(())
    }

    fn query<P: ExecutionProvider>(
        &self,
        provider: &P,
        p: &Parameters,
        key: &[f32],
        query_id: usize,
        metrics: &mut Metrics,
    ) -> Result<Prediction> {
        let mut transaction = provider.begin()?;
        let mut selected = Some(self.null_reference);
        let read = if p.arm == Arm::NoHistory {
            dense(transaction.read(self.null_reference)?)?
        } else {
            let query = apply(provider, &p.query, key, metrics)?;
            let mut cells: Vec<_> = self.cells.iter().flatten().collect();
            cells.sort_by_key(|cell| cell.written_at);
            let mut scores = vec![p.null_score];
            let mut references = vec![self.null_reference];
            for cell in cells {
                let dot: f32 = query
                    .iter()
                    .zip(&cell.key)
                    .map(|(left, right)| left * right)
                    .sum();
                let age = ((self.writes - cell.written_at) as f32).ln_1p();
                scores.push(dot / 8_f32.sqrt() + p.age_coefficient * age);
                references.push(cell.reference);
                metrics.nominal_scalar_ops += 21; // dot, scale, age subtraction/log, multiply, add.
                metrics.descriptor_read_bytes += 56;
            }
            if scores.iter().any(|score| !score.is_finite()) {
                return Err(Error::new(
                    "nonfinite_computation",
                    "routing score overflowed",
                ));
            }
            if p.arm == Arm::Dense {
                selected = None;
                let max = scores.iter().copied().fold(f32::NEG_INFINITY, f32::max);
                let weights: Vec<_> = scores.iter().map(|score| (*score - max).exp()).collect();
                let total: f32 = weights.iter().sum();
                let mut combined = vec![0.0; 8];
                for (reference, weight) in references.iter().zip(weights) {
                    let payload = dense(transaction.read(*reference)?)?;
                    if payload.len() != 8 {
                        return Err(Error::new("invalid_state", "payload shape changed"));
                    }
                    for (out, value) in combined.iter_mut().zip(payload) {
                        *out += weight / total * value;
                    }
                }
                metrics.nominal_scalar_ops += references.len() as u64 * 28; // max/softmax and eight weighted coordinates.
                combined
            } else {
                let reference = provider.select(&Value::Dense { data: scores }, &references)?;
                selected = Some(reference);
                metrics.nominal_scalar_ops += references.len().saturating_sub(1) as u64;
                dense(transaction.read(reference)?)?
            }
        };
        metrics.payload_reads += transaction.read_metrics().payload_reads;
        metrics.payload_read_bytes += transaction.read_metrics().payload_bytes;
        if read.len() != 8 {
            return Err(Error::new("invalid_state", "payload shape changed"));
        }
        let logits = apply(provider, &p.decoder, &read, metrics)?;
        let prediction =
            logits.iter().enumerate().fold(
                0,
                |best, (i, value)| if *value > logits[best] { i } else { best },
            );
        metrics.queries += 1;
        Ok(Prediction {
            query_id,
            logits,
            prediction,
            selected,
        })
    }
}

pub fn evaluate_episode<P: ExecutionProvider>(
    provider: &P,
    parameters: &Parameters,
    episode: &Episode,
) -> Result<(Vec<Prediction>, Metrics)> {
    if episode.observations.len() > 136 || episode.id.len() > 128 {
        return Err(Error::new("run_budget", "episode exceeds input admission"));
    }
    let mut state = State::initialize(provider, parameters)?;
    let mut metrics = Metrics::default();
    let mut predictions = Vec::new();
    for observation in &episode.observations {
        if let Some(prediction) = state.step(provider, parameters, observation, &mut metrics)? {
            if prediction.query_id != predictions.len() {
                return Err(Error::new(
                    "invalid_observation",
                    "query IDs must be consecutive",
                ));
            }
            predictions.push(prediction);
        }
    }
    if predictions.len() != 8 {
        return Err(Error::new(
            "invalid_observation",
            "episode must contain eight queries",
        ));
    }
    Ok((predictions, metrics))
}
