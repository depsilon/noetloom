use serde::{Deserialize, Serialize};

use crate::{Error, Result};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CellRef {
    pub id: u64,
    pub revision: u64,
}

impl CellRef {
    pub fn validate(&self) -> Result<()> {
        if self.revision == 0 {
            return Err(Error::new(
                "invalid_value",
                "cell reference revision must be at least 1",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Value {
    Dense { data: Vec<f32> },
    Bytes { data: Vec<u8> },
    Refs { data: Vec<CellRef> },
}

impl Value {
    pub fn logical_bytes(&self) -> Result<u64> {
        let (len, bytes_per_element) = match self {
            Self::Dense { data } => (data.len(), 4_u64),
            Self::Bytes { data } => (data.len(), 1_u64),
            Self::Refs { data } => (data.len(), 16_u64),
        };
        let len = u64::try_from(len)
            .map_err(|_| Error::new("invalid_value", "value length exceeds u64"))?;
        len.checked_mul(bytes_per_element)
            .ok_or_else(|| Error::new("invalid_value", "logical value size overflows u64"))
    }

    pub fn validate(&self, max_bytes: u64) -> Result<()> {
        let size = self.logical_bytes()?;
        if size == 0 {
            return Err(Error::new(
                "invalid_value",
                "value payload must not be empty",
            ));
        }
        if size > max_bytes {
            return Err(Error::new(
                "invalid_value",
                format!("value payload is {size} bytes, exceeding limit {max_bytes}"),
            ));
        }
        match self {
            Self::Dense { data } if data.iter().any(|value| !value.is_finite()) => Err(Error::new(
                "invalid_value",
                "dense value contains a nonfinite number",
            )),
            Self::Refs { data } => data.iter().try_for_each(CellRef::validate),
            _ => Ok(()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{CellRef, Value};

    #[test]
    fn values_report_storage_size_and_enforce_payload_budgets() {
        let dense = Value::Dense {
            data: vec![1.0, -2.0],
        };
        let bytes = Value::Bytes {
            data: vec![0, 1, 2],
        };
        let refs = Value::Refs {
            data: vec![CellRef { id: 0, revision: 1 }],
        };

        assert_eq!(dense.logical_bytes().unwrap(), 8);
        assert_eq!(bytes.logical_bytes().unwrap(), 3);
        assert_eq!(refs.logical_bytes().unwrap(), 16);
        assert!(dense.validate(8).is_ok());
        assert_eq!(bytes.validate(2).unwrap_err().code, "invalid_value");
        assert!(refs.validate(16).is_ok());
    }

    #[test]
    fn values_reject_empty_nonfinite_and_invalid_references() {
        assert_eq!(
            Value::Bytes { data: vec![] }.validate(0).unwrap_err().code,
            "invalid_value"
        );
        assert_eq!(
            Value::Dense {
                data: vec![f32::INFINITY]
            }
            .validate(4)
            .unwrap_err()
            .code,
            "invalid_value"
        );
        assert_eq!(
            Value::Refs {
                data: vec![CellRef { id: 9, revision: 0 }],
            }
            .validate(16)
            .unwrap_err()
            .code,
            "invalid_value"
        );
    }
}
