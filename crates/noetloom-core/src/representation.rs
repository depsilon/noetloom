//! EXP-0004 component probe: an input-conditioned intermediate field, not a foundation claim.
use crate::operator::{Activation, Affine};
use crate::provider::ExecutionProvider;
use crate::value::Value;
use crate::{Error, Result};
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Arm {
    FixedSmall,
    FixedLarge,
    Conditional,
    Static,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Parameters {
    pub schema_version: String,
    pub arm: Arm,
    pub seed: u32,
    pub step: u32,
    pub construction: Vec<Affine>,
    pub static_scores: Vec<f32>,
    pub solver: Vec<Affine>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Sample {
    pub values: Vec<f32>,
}

impl Sample {
    pub fn validate(&self) -> Result<()> {
        if self.values.len() != 64 || self.values.iter().any(|x| !x.is_finite() || x.abs() > 2.0) {
            return Err(Error::new(
                "invalid_field",
                "expected 64 finite values in [-2,2]",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Inputs {
    pub schema_version: String,
    pub samples: Vec<Sample>,
}

impl Inputs {
    pub fn validate(&self) -> Result<()> {
        if self.schema_version != "noetloom.representation_inputs.v1"
            || self.samples.is_empty()
            || self.samples.len() > 512
        {
            return Err(Error::new(
                "invalid_inputs",
                "expected 1–512 registered field samples",
            ));
        }
        for sample in &self.samples {
            sample.validate()?;
        }
        Ok(())
    }
}

pub struct Constructed {
    pub intermediate: Vec<f32>,
    pub transport: Option<Vec<f32>>,
    pub nominal_scalar_ops: u64,
}

fn dense(value: Value) -> Result<Vec<f32>> {
    match value {
        Value::Dense { data } => Ok(data),
        _ => Err(Error::new(
            "provider_result",
            "affine provider returned a non-dense value",
        )),
    }
}

pub fn transport<P: ExecutionProvider>(
    provider: &P,
    matrix: &[f32],
    values: &[f32],
) -> Result<Vec<f32>> {
    if matrix.len() != 1024
        || matrix.iter().any(|x| !x.is_finite() || *x < 0.0)
        || matrix
            .as_chunks::<64>()
            .0
            .iter()
            .any(|row| (row.iter().sum::<f32>() - 1.0).abs() > 1e-4)
    {
        return Err(Error::new(
            "invalid_transport",
            "transport rows must be finite probabilities",
        ));
    }
    dense(provider.affine(
        &Affine {
            input_dim: 64,
            output_dim: 16,
            weights: matrix.to_vec(),
            bias: vec![0.0; 16],
            activation: Activation::Identity,
        },
        &Value::Dense {
            data: values.to_vec(),
        },
    )?)
}

impl Parameters {
    pub fn intermediate_width(&self) -> usize {
        if matches!(self.arm, Arm::FixedSmall | Arm::FixedLarge) {
            64
        } else {
            16
        }
    }

    pub fn parameter_count(&self) -> usize {
        self.construction
            .iter()
            .chain(self.solver.iter())
            .map(|a| a.weights.len() + a.bias.len())
            .sum::<usize>()
            + self.static_scores.len()
    }

    pub fn validate(&self) -> Result<()> {
        if self.schema_version != "noetloom.representation_parameters.v1" || self.step > 1024 {
            return Err(Error::new(
                "invalid_parameters",
                "unsupported representation parameter identity",
            ));
        }
        let hidden = if self.arm == Arm::FixedLarge { 160 } else { 32 };
        let expected_construction = if self.arm == Arm::Conditional {
            vec![(64, 16), (16, 1024)]
        } else {
            vec![]
        };
        let expected_solver = vec![
            (self.intermediate_width(), hidden),
            (hidden, hidden),
            (hidden, 2),
        ];
        for (layers, expected) in [
            (&self.construction, expected_construction),
            (&self.solver, expected_solver),
        ] {
            if layers.len() != expected.len() {
                return Err(Error::new(
                    "invalid_parameters",
                    "layer count differs from registered arm",
                ));
            }
            for (index, (layer, shape)) in layers.iter().zip(expected).enumerate() {
                layer.validate()?;
                let activation = if index + 1 == layers.len() {
                    Activation::Identity
                } else {
                    Activation::Tanh
                };
                if (layer.input_dim, layer.output_dim) != shape || layer.activation != activation {
                    return Err(Error::new(
                        "invalid_parameters",
                        "layer shape or activation differs",
                    ));
                }
            }
        }
        let expected_scores = if self.arm == Arm::Static { 1024 } else { 0 };
        if self.static_scores.len() != expected_scores
            || self.static_scores.iter().any(|x| !x.is_finite())
        {
            return Err(Error::new(
                "invalid_parameters",
                "static transport differs from registered arm",
            ));
        }
        Ok(())
    }

    pub fn construct<P: ExecutionProvider>(
        &self,
        provider: &P,
        sample: &Sample,
    ) -> Result<Constructed> {
        self.validate()?;
        sample.validate()?;
        if matches!(self.arm, Arm::FixedSmall | Arm::FixedLarge) {
            return Ok(Constructed {
                intermediate: sample.values.clone(),
                transport: None,
                nominal_scalar_ops: 0,
            });
        }
        let mut operations = 0;
        let mut scores = if self.arm == Arm::Conditional {
            let mut current = Value::Dense {
                data: sample.values.clone(),
            };
            for layer in &self.construction {
                operations += layer.scalar_ops()?;
                current = provider.affine(layer, &current)?;
            }
            dense(current)?
        } else {
            self.static_scores.clone()
        };
        for row in scores.as_chunks_mut::<64>().0 {
            let maximum = row.iter().copied().fold(f32::NEG_INFINITY, f32::max);
            let mut total = 0.0;
            for value in row.iter_mut() {
                *value = (*value - maximum).exp();
                total += *value;
            }
            for value in row {
                *value /= total;
            }
        }
        operations += 16 * (5 * 64 - 2) + Self::transport_ops();
        let intermediate = transport(provider, &scores, &sample.values)?;
        Ok(Constructed {
            intermediate,
            transport: Some(scores),
            nominal_scalar_ops: operations,
        })
    }

    pub const fn transport_ops() -> u64 {
        2 * 64 * 16 + 16
    }

    pub fn solver_ops(&self) -> Result<u64> {
        self.solver
            .iter()
            .try_fold(0, |sum, layer| Ok(sum + layer.scalar_ops()?))
    }

    pub fn solve<P: ExecutionProvider>(
        &self,
        provider: &P,
        intermediate: &[f32],
    ) -> Result<Vec<f32>> {
        self.validate()?;
        if intermediate.len() != self.intermediate_width()
            || intermediate.iter().any(|x| !x.is_finite())
        {
            return Err(Error::new(
                "invalid_intermediate",
                "intermediate has wrong width or nonfinite values",
            ));
        }
        let mut value = Value::Dense {
            data: intermediate.to_vec(),
        };
        for layer in &self.solver {
            value = provider.affine(layer, &value)?;
        }
        dense(value)
    }
}
