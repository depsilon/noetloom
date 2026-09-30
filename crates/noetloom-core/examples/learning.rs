//! Observation-only native evaluator; parameter artifacts contain no pretrained components.
use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::path::Path;
use std::time::Instant;

use noetloom_core::learning::{Episode, Metrics, Parameters, State, evaluate_episode};
use noetloom_core::memory::MemoryStore;
use noetloom_core::store::{Store, StoreLimits, sha256};
use noetloom_core::{Error, Result};
use serde_json::{Value, json};

fn read(path: &str, maximum: u64) -> Result<Vec<u8>> {
    let mut bytes = Vec::new();
    fs::File::open(path)?
        .take(maximum + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() as u64 > maximum {
        return Err(Error::new("input_budget", "input exceeds byte admission"));
    }
    Ok(bytes)
}

fn build_identity() -> Value {
    serde_json::from_str(include_str!(concat!(
        env!("OUT_DIR"),
        "/build-identity.json"
    )))
    .expect("compiled build identity")
}

fn write(path: &str, value: &Value) -> Result<()> {
    let bytes = serde_json::to_vec(value)?;
    if bytes.len() > 8 * 1024 * 1024 {
        return Err(Error::new("output_budget", "native output exceeds 8 MiB"));
    }
    OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)?
        .write_all(&bytes)?;
    Ok(())
}

fn main_result(arguments: &[String]) -> Result<()> {
    if arguments.len() < 5 {
        return Err(Error::new(
            "usage",
            "learning evaluate|persist|resume PARAMETERS OBSERVATIONS OUTPUT [STATE_DIR SPLIT_INDEX]",
        ));
    }
    let started = Instant::now();
    let parameter_bytes = read(&arguments[2], 64 * 1024)?;
    let p: Parameters = serde_json::from_slice(&parameter_bytes)?;
    p.validate()?;
    let input_bytes = read(&arguments[3], 8 * 1024 * 1024)?;
    let episodes: Vec<Episode> = serde_json::from_slice(&input_bytes)?;
    let mut results = Vec::new();
    match arguments[1].as_str() {
        "evaluate" => {
            if arguments.len() != 5 || episodes.is_empty() || episodes.len() > 512 {
                return Err(Error::new(
                    "input_budget",
                    "evaluate requires 1–512 episodes",
                ));
            }
            for episode in &episodes {
                let provider = MemoryStore::new(33, 4096)?;
                let (predictions, metrics) = evaluate_episode(&provider, &p, episode)?;
                results.push(
                    json!({"id": episode.id, "predictions": predictions, "metrics": metrics}),
                );
            }
        }
        mode @ ("persist" | "resume") => {
            if arguments.len() != 7 || episodes.len() != 1 {
                return Err(Error::new(
                    "usage",
                    "persistence expects one episode, state path, and split index",
                ));
            }
            let directory = Path::new(&arguments[5]);
            let split: usize = arguments[6]
                .parse()
                .map_err(|_| Error::new("usage", "invalid split index"))?;
            let episode = &episodes[0];
            if split == 0 || split >= episode.observations.len() || episode.observations.len() > 136
            {
                return Err(Error::new("input_budget", "invalid persistent split"));
            }
            let meta_path = directory.join("metadata.json");
            let store_path = directory.join("state");
            let mut state: State = if mode == "persist" {
                fs::create_dir(directory)?;
                let provider = Store::create(&store_path, StoreLimits::default())?;
                State::initialize(&provider, &p)?
            } else {
                let checkpoint: Value = serde_json::from_slice(&read(
                    meta_path
                        .to_str()
                        .ok_or_else(|| Error::new("usage", "non-UTF8 metadata path"))?,
                    64 * 1024,
                )?)?;
                if checkpoint["parameter_sha256"] != sha256(&parameter_bytes)
                    || checkpoint["input_sha256"] != sha256(&input_bytes)
                    || checkpoint["split"] != split
                    || checkpoint["build"] != build_identity()
                {
                    return Err(Error::new(
                        "identity_mismatch",
                        "persistent state was built with different inputs, parameters, or code",
                    ));
                }
                serde_json::from_value(checkpoint["state"].clone())?
            };
            state.validate()?;
            let range = if mode == "persist" {
                0..split
            } else {
                split..episode.observations.len()
            };
            let mut metrics = Metrics::default();
            let mut predictions = Vec::new();
            for index in range {
                // Persistent Store pins an immutable snapshot; reopen after each committed write.
                let provider = Store::open(&store_path, StoreLimits::default())?;
                if let Some(prediction) =
                    state.step(&provider, &p, &episode.observations[index], &mut metrics)?
                {
                    predictions.push(prediction);
                }
            }
            if mode == "persist" {
                write(
                    meta_path
                        .to_str()
                        .ok_or_else(|| Error::new("usage", "non-UTF8 metadata path"))?,
                    &json!({
                    "state": state, "parameter_sha256": sha256(&parameter_bytes),
                    "input_sha256": sha256(&input_bytes), "split": split, "build": build_identity()}),
                )?;
            }
            results.push(json!({"id": episode.id, "predictions": predictions, "metrics": metrics}));
        }
        _ => return Err(Error::new("usage", "unknown evaluation mode")),
    }
    write(
        &arguments[4],
        &json!({"schema_version": "noetloom.native_learning.v1", "build": build_identity(),
        "parameter_sha256": sha256(&parameter_bytes), "input_sha256": sha256(&input_bytes),
        "results": results, "elapsed_seconds": started.elapsed().as_secs_f64(),
        "scope": "Registered state-cell and read-allocation scaffolds; learned artifact provenance must be verified by the experiment driver."}),
    )
}

fn main() {
    if let Err(error) = main_result(&std::env::args().collect::<Vec<_>>()) {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
