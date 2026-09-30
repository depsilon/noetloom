use serde::{Deserialize, Serialize};

use crate::{Error, Result, value::Value};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Activation {
    Identity,
    Tanh,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Affine {
    pub input_dim: usize,
    pub output_dim: usize,
    /// Row-major matrix with `output_dim` rows and `input_dim` columns.
    pub weights: Vec<f32>,
    pub bias: Vec<f32>,
    pub activation: Activation,
}

impl Affine {
    pub fn validate(&self) -> Result<()> {
        const MAX_DIM: usize = 4096;
        const MAX_WEIGHTS: usize = 1_048_576;

        if !(1..=MAX_DIM).contains(&self.input_dim) || !(1..=MAX_DIM).contains(&self.output_dim) {
            return Err(Error::new(
                "invalid_operator",
                "affine dimensions must be between 1 and 4096",
            ));
        }
        let weight_count = self
            .input_dim
            .checked_mul(self.output_dim)
            .ok_or_else(|| Error::new("invalid_operator", "affine weight count overflows"))?;
        if weight_count > MAX_WEIGHTS {
            return Err(Error::new(
                "invalid_operator",
                "affine operator exceeds the 1,048,576 weight limit",
            ));
        }
        if self.weights.len() != weight_count || self.bias.len() != self.output_dim {
            return Err(Error::new(
                "invalid_operator",
                "affine weight or bias length does not match its dimensions",
            ));
        }
        if self
            .weights
            .iter()
            .chain(self.bias.iter())
            .any(|value| !value.is_finite())
        {
            return Err(Error::new(
                "invalid_operator",
                "affine parameters must all be finite",
            ));
        }
        Ok(())
    }

    /// Nominal scalar work: multiply/add per weight, bias addition, and one
    /// operation per output for the optional tanh activation.
    pub fn scalar_ops(&self) -> Result<u64> {
        self.validate()?;
        let inputs = u64::try_from(self.input_dim)
            .map_err(|_| Error::new("invalid_operator", "input dimension exceeds u64"))?;
        let outputs = u64::try_from(self.output_dim)
            .map_err(|_| Error::new("invalid_operator", "output dimension exceeds u64"))?;
        let products = inputs
            .checked_mul(outputs)
            .and_then(|count| count.checked_mul(2))
            .ok_or_else(|| Error::new("invalid_operator", "scalar operation count overflows"))?;
        let bias_ops = outputs;
        let activation_ops = if self.activation == Activation::Tanh {
            outputs
        } else {
            0
        };
        products
            .checked_add(bias_ops)
            .and_then(|count| count.checked_add(activation_ops))
            .ok_or_else(|| Error::new("invalid_operator", "scalar operation count overflows"))
    }

    pub fn apply(&self, input: &Value) -> Result<Value> {
        self.validate()?;
        let Value::Dense { data } = input else {
            return Err(Error::new(
                "invalid_input",
                "affine operator requires a dense input value",
            ));
        };
        if data.len() != self.input_dim {
            return Err(Error::new(
                "invalid_input",
                format!(
                    "affine input has dimension {}, expected {}",
                    data.len(),
                    self.input_dim
                ),
            ));
        }
        if data.iter().any(|value| !value.is_finite()) {
            return Err(Error::new(
                "invalid_input",
                "affine input contains a nonfinite number",
            ));
        }

        let mut output = Vec::with_capacity(self.output_dim);
        for (row, bias) in self.bias.iter().enumerate() {
            let start = row * self.input_dim;
            let mut sum = *bias;
            for (weight, input_value) in self.weights[start..start + self.input_dim]
                .iter()
                .zip(data.iter())
            {
                sum += weight * input_value;
            }
            let value = match self.activation {
                Activation::Identity => sum,
                Activation::Tanh => sum.tanh(),
            };
            if !value.is_finite() {
                return Err(Error::new(
                    "invalid_operator",
                    "affine output contains a nonfinite number",
                ));
            }
            output.push(value);
        }
        Ok(Value::Dense { data: output })
    }
}

#[cfg(test)]
mod tests {
    use super::{Activation, Affine};
    use crate::value::Value;

    fn matrix_fixture(activation: Activation) -> Affine {
        Affine {
            input_dim: 2,
            output_dim: 2,
            weights: vec![1.0, 2.0, -1.0, 3.0],
            bias: vec![0.5, -2.0],
            activation,
        }
    }

    #[test]
    fn affine_computes_row_major_matrix_and_counts_nominal_work() {
        let affine = matrix_fixture(Activation::Identity);
        assert_eq!(
            affine
                .apply(&Value::Dense {
                    data: vec![2.0, 3.0]
                })
                .unwrap(),
            Value::Dense {
                data: vec![8.5, 5.0]
            }
        );
        assert_eq!(affine.scalar_ops().unwrap(), 10);
    }

    #[test]
    fn affine_applies_tanh_per_output() {
        let affine = Affine {
            input_dim: 1,
            output_dim: 1,
            weights: vec![2.0],
            bias: vec![0.0],
            activation: Activation::Tanh,
        };
        let Value::Dense { data } = affine.apply(&Value::Dense { data: vec![0.5] }).unwrap() else {
            panic!("affine output should be dense");
        };
        assert!((data[0] - 1.0_f32.tanh()).abs() < 1e-6);
        assert_eq!(affine.scalar_ops().unwrap(), 4);
    }

    #[test]
    fn affine_rejects_wrong_shapes_nonfinite_values_and_overflowing_dimensions() {
        let affine = matrix_fixture(Activation::Identity);
        assert_eq!(
            affine
                .apply(&Value::Dense { data: vec![1.0] })
                .unwrap_err()
                .code,
            "invalid_input"
        );
        assert_eq!(
            affine
                .apply(&Value::Bytes { data: vec![1, 2] })
                .unwrap_err()
                .code,
            "invalid_input"
        );
        assert_eq!(
            affine
                .apply(&Value::Dense {
                    data: vec![f32::NAN, 1.0]
                })
                .unwrap_err()
                .code,
            "invalid_input"
        );

        let mut bad_params = affine.clone();
        bad_params.weights[0] = f32::INFINITY;
        assert_eq!(bad_params.validate().unwrap_err().code, "invalid_operator");

        let overflowing_dimensions = Affine {
            input_dim: usize::MAX,
            output_dim: 2,
            weights: vec![],
            bias: vec![],
            activation: Activation::Identity,
        };
        assert_eq!(
            overflowing_dimensions.validate().unwrap_err().code,
            "invalid_operator"
        );
    }

    #[test]
    fn affine_rejects_nonfinite_computed_outputs() {
        let affine = Affine {
            input_dim: 1,
            output_dim: 1,
            weights: vec![f32::MAX],
            bias: vec![0.0],
            activation: Activation::Identity,
        };
        assert_eq!(
            affine
                .apply(&Value::Dense { data: vec![2.0] })
                .unwrap_err()
                .code,
            "invalid_operator"
        );
    }
}
