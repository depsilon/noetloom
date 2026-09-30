//! Independent EXP-0004 evaluator and resumable intermediate-state execution.
use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::path::Path;
use std::time::Instant;

use noetloom_core::memory::MemoryStore;
use noetloom_core::provider::{ExecutionProvider, StateTransaction};
use noetloom_core::representation::{Arm, Inputs, Parameters, transport};
use noetloom_core::store::{Store, StoreLimits, sha256};
use noetloom_core::value::{CellRef, Value};
use noetloom_core::{Error, Result};
use serde_json::{Value as Json, json};

fn read(path: &str, maximum: u64) -> Result<Vec<u8>> {
    let mut bytes = Vec::new();
    fs::File::open(path)?
        .take(maximum + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() as u64 > maximum {
        return Err(Error::new("input_budget", "input exceeds admission"));
    }
    Ok(bytes)
}

fn write(path: &Path, value: &Json) -> Result<()> {
    let bytes = serde_json::to_vec(value)?;
    if bytes.len() > 8 * 1024 * 1024 {
        return Err(Error::new("output_budget", "receipt exceeds 8 MiB"));
    }
    let mut handle = OpenOptions::new().write(true).create_new(true).open(path)?;
    handle.write_all(&bytes)?;
    handle.sync_all()?;
    Ok(())
}

fn build() -> Json {
    serde_json::from_str(include_str!(concat!(
        env!("OUT_DIR"),
        "/build-identity.json"
    )))
    .expect("compiled build identity")
}

fn selected(logits: &[f32]) -> usize {
    usize::from(logits[1] > logits[0])
}

fn round_trip<P: ExecutionProvider>(provider: &P, values: &[f32]) -> Result<(Vec<f32>, Json)> {
    let mut transaction = provider.begin()?;
    let reference = transaction.write(
        0,
        None,
        Value::Dense {
            data: values.to_vec(),
        },
        1024,
    )?;
    let commit = transaction.commit(4096)?;
    let mut transaction = provider.begin()?;
    let Value::Dense { data } = transaction.read(reference)? else {
        return Err(Error::new("invalid_intermediate", "state is not dense"));
    };
    Ok((
        data,
        json!({"commit": commit, "activation_reads": transaction.read_metrics()}),
    ))
}

fn main_result(args: &[String]) -> Result<()> {
    if args.len() < 5 {
        return Err(Error::new(
            "usage",
            "representation evaluate|persist|resume PARAMETERS INPUTS OUTPUT [GROUP_SIZE|STATE_DIR]",
        ));
    }
    let start = Instant::now();
    let raw_parameters = read(&args[2], 2 * 1024 * 1024)?;
    let parameters: Parameters = serde_json::from_slice(&raw_parameters)?;
    parameters.validate()?;
    let raw_inputs = read(&args[3], 2 * 1024 * 1024)?;
    let inputs: Inputs = serde_json::from_slice(&raw_inputs)?;
    inputs.validate()?;
    let mut rows = Vec::new();
    let mut nominal_scalar_ops = 0_u64;
    let mut entropy_sum = 0.0_f64;
    let mut matrix_sum = vec![0.0_f64; 1024];
    let mut matrix_squared_sum = vec![0.0_f64; 1024];
    let mut matrix_count = 0;
    match args[1].as_str() {
        "evaluate" => {
            if args.len() != 6 {
                return Err(Error::new(
                    "usage",
                    "evaluate requires a shift-group size (zero for ordinary inference)",
                ));
            }
            let group: usize = args[5]
                .parse()
                .map_err(|_| Error::new("usage", "invalid group size"))?;
            if group != 0
                && (parameters.arm != Arm::Conditional
                    || group < 2
                    || !inputs.samples.len().is_multiple_of(group))
            {
                return Err(Error::new(
                    "invalid_intervention",
                    "shift requires complete conditional groups",
                ));
            }
            let provider = MemoryStore::new(1, 1024)?;
            let constructed = inputs
                .samples
                .iter()
                .map(|sample| parameters.construct(&provider, sample))
                .collect::<Result<Vec<_>>>()?;
            for (index, (sample, own)) in inputs.samples.iter().zip(&constructed).enumerate() {
                let mut intermediate = own.intermediate.clone();
                nominal_scalar_ops += own.nominal_scalar_ops;
                let donor = match index.checked_div(group) {
                    None => index,
                    Some(block) => block * group + (index % group + group - 1) % group,
                };
                if let Some(matrix) = &constructed[donor].transport {
                    matrix_count += 1;
                    for (position, value) in matrix.iter().enumerate() {
                        let value = f64::from(*value);
                        entropy_sum -= value * value.max(f64::MIN_POSITIVE).ln();
                        matrix_sum[position] += value;
                        matrix_squared_sum[position] += value * value;
                    }
                    if group != 0 {
                        intermediate = transport(&provider, matrix, &sample.values)?;
                        nominal_scalar_ops += Parameters::transport_ops();
                    }
                }
                // Every independent problem starts with empty state; no cross-example memory.
                let state = MemoryStore::new(1, 1024)?;
                let (intermediate, receipt) = round_trip(&state, &intermediate)?;
                let logits = parameters.solve(&state, &intermediate)?;
                nominal_scalar_ops += parameters.solver_ops()?;
                rows.push(json!({"intermediate": intermediate, "prediction": selected(&logits), "logits": logits, "state": receipt}));
            }
        }
        mode @ ("persist" | "resume") => {
            if args.len() != 6 || inputs.samples.len() != 1 {
                return Err(Error::new(
                    "usage",
                    "persistence requires one sample and a state directory",
                ));
            }
            let directory = Path::new(&args[5]);
            let metadata = directory.join("metadata.json");
            let store_path = directory.join("state");
            if mode == "persist" {
                fs::create_dir(directory)?;
                let provider = Store::create(&store_path, StoreLimits::default())?;
                let prepared = parameters.construct(&provider, &inputs.samples[0])?;
                let mut transaction = provider.begin()?;
                let reference = transaction.write(
                    0,
                    None,
                    Value::Dense {
                        data: prepared.intermediate.clone(),
                    },
                    1024,
                )?;
                let commit = transaction.commit_with_validation_limit(4096)?;
                write(
                    &metadata,
                    &json!({"schema_version": "noetloom.representation_checkpoint.v1", "reference": reference,
                    "parameter_sha256": sha256(&raw_parameters), "input_sha256": sha256(&raw_inputs), "build": build()}),
                )?;
                nominal_scalar_ops = prepared.nominal_scalar_ops;
                rows.push(json!({"intermediate": prepared.intermediate, "commit": commit}));
            } else {
                let metadata: Json = serde_json::from_slice(&read(
                    metadata
                        .to_str()
                        .ok_or_else(|| Error::new("usage", "non-UTF8 state path"))?,
                    128 * 1024,
                )?)?;
                if metadata["schema_version"] != "noetloom.representation_checkpoint.v1"
                    || metadata["parameter_sha256"] != sha256(&raw_parameters)
                    || metadata["input_sha256"] != sha256(&raw_inputs)
                    || metadata["build"] != build()
                {
                    return Err(Error::new(
                        "identity_mismatch",
                        "intermediate was built with different parameters, input or code",
                    ));
                }
                let reference: CellRef = serde_json::from_value(metadata["reference"].clone())?;
                let provider = Store::open(&store_path, StoreLimits::default())?;
                let mut transaction = provider.begin()?;
                let Value::Dense { data: intermediate } = transaction.read(reference)? else {
                    return Err(Error::new(
                        "invalid_intermediate",
                        "persisted state is not dense",
                    ));
                };
                let logits = parameters.solve(&provider, &intermediate)?;
                nominal_scalar_ops = parameters.solver_ops()?;
                rows.push(json!({"intermediate": intermediate, "prediction": selected(&logits), "logits": logits,
                    "activation_reads": transaction.read_metrics(), "metadata_bytes_read": provider.metadata_bytes_read()}));
            }
        }
        _ => return Err(Error::new("usage", "unknown representation mode")),
    }
    let (entropy, variance) = if matrix_count == 0 {
        (None, None)
    } else {
        let count = f64::from(matrix_count);
        let variance = matrix_sum
            .iter()
            .zip(matrix_squared_sum)
            .map(|(sum, squared)| squared / count - (sum / count).powi(2))
            .sum::<f64>()
            / 1024.0;
        (Some(entropy_sum / (count * 16.0)), Some(variance.max(0.0)))
    };
    write(
        Path::new(&args[4]),
        &json!({"schema_version": "noetloom.native_representation.v1", "build": build(),
        "parameter_sha256": sha256(&raw_parameters), "input_sha256": sha256(&raw_inputs),
        "parameter_count": parameters.parameter_count(), "rows": rows, "nominal_scalar_ops": nominal_scalar_ops,
        "raw_input_bytes": inputs.samples.len() * 64 * 4, "transport_entropy": entropy, "transport_variance": variance,
        "elapsed_seconds": start.elapsed().as_secs_f64(),
        "scope": "Registered EXP-0004 component; nominal model arithmetic excludes validation, evidence statistics, hashing and serialization, whose time remains in elapsed_seconds."}),
    )
}

fn main() {
    if let Err(error) = main_result(&std::env::args().collect::<Vec<_>>()) {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
