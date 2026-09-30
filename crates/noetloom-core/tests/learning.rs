use noetloom_core::learning::{Arm, Metrics, Observation, Parameters, State};
use noetloom_core::memory::MemoryStore;
use noetloom_core::operator::{Activation, Affine};
use noetloom_core::provider::{ExecutionProvider, StateTransaction};
use noetloom_core::value::{CellRef, Value};

fn identity_prefix(input_dim: usize, output_dim: usize) -> Affine {
    let mut weights = vec![0.0; input_dim * output_dim];
    for index in 0..output_dim.min(input_dim) {
        weights[index * input_dim + index] = 1.0;
    }
    Affine {
        input_dim,
        output_dim,
        weights,
        bias: vec![0.0; output_dim],
        activation: Activation::Identity,
    }
}

fn fixture_parameters(arm: Arm) -> Parameters {
    // Hand-authored step-zero fixture for operation checks; this is not learning evidence.
    Parameters {
        schema_version: "noetloom.cell_parameters.v1".into(),
        arm,
        seed: 0,
        step: 0,
        query: identity_prefix(16, 8),
        key: identity_prefix(16, 8),
        encoder: Affine {
            input_dim: 5,
            output_dim: 8,
            weights: {
                let mut weights = vec![0.0; 40];
                for index in 0..5 {
                    weights[index * 5 + index] = 1.0;
                }
                weights
            },
            bias: vec![0.0; 8],
            activation: Activation::Tanh,
        },
        decoder: Affine {
            input_dim: 8,
            output_dim: 5,
            weights: {
                let mut weights = vec![0.0; 40];
                for index in 0..5 {
                    weights[index * 8 + index] = 1.0;
                }
                weights
            },
            bias: vec![0.0; 5],
            activation: Activation::Identity,
        },
        age_coefficient: -0.2,
        null_score: -100.0,
        null_payload: vec![0.0; 8],
    }
}

fn key() -> Vec<f32> {
    vec![1.0; 16]
}

fn query_id(id: usize) -> Observation {
    Observation::Query {
        key: key(),
        query_id: id,
    }
}

fn write_class(value: usize) -> Observation {
    Observation::Write { key: key(), value }
}

fn prediction_for(
    state: &mut State,
    store: &MemoryStore,
    parameters: &Parameters,
    observation: Observation,
    metrics: &mut Metrics,
) -> usize {
    state
        .step(store, parameters, &observation, metrics)
        .unwrap()
        .unwrap()
        .prediction
}

#[test]
fn resident_store_stages_atomically_and_rejects_stale_transactions() {
    let store = MemoryStore::new(1, 32).unwrap();
    let mut dropped = store.begin().unwrap();
    dropped
        .write(1, None, Value::Dense { data: vec![1.0] }, 32)
        .unwrap();
    drop(dropped);
    assert_eq!(
        store
            .begin()
            .unwrap()
            .read_admission(CellRef { id: 1, revision: 1 })
            .unwrap_err()
            .code,
        "stale_reference"
    );

    let mut first = store.begin().unwrap();
    let mut second = store.begin().unwrap();
    first
        .write(1, None, Value::Dense { data: vec![1.0] }, 32)
        .unwrap();
    second
        .write(1, None, Value::Dense { data: vec![2.0] }, 32)
        .unwrap();
    first.commit(32).unwrap();
    assert_eq!(second.commit(32).unwrap_err().code, "write_conflict");

    let mut current = store.begin().unwrap();
    assert_eq!(
        current.read(CellRef { id: 1, revision: 1 }).unwrap(),
        Value::Dense { data: vec![1.0] }
    );
    assert_eq!(
        current
            .write(1, Some(1), Value::Bytes { data: vec![0; 33] }, 32)
            .unwrap_err()
            .code,
        "invalid_value"
    );
    assert_eq!(
        current
            .write(1, Some(2), Value::Dense { data: vec![3.0] }, 32)
            .unwrap_err()
            .code,
        "write_conflict"
    );
    assert_eq!(
        current.read(CellRef { id: 1, revision: 1 }).unwrap(),
        Value::Dense { data: vec![1.0] }
    );
}

#[test]
fn selective_fixture_recalls_revisions_and_tombstones_with_sparse_reads() {
    let store = MemoryStore::new(33, 4096).unwrap();
    let parameters = fixture_parameters(Arm::Selective);
    parameters.validate().unwrap();
    let mut state = State::initialize(&store, &parameters).unwrap();
    let mut metrics = Metrics::default();

    state
        .step(&store, &parameters, &write_class(1), &mut metrics)
        .unwrap();
    assert_eq!(
        prediction_for(&mut state, &store, &parameters, query_id(0), &mut metrics),
        1
    );
    state
        .step(&store, &parameters, &write_class(3), &mut metrics)
        .unwrap();
    assert_eq!(
        prediction_for(&mut state, &store, &parameters, query_id(1), &mut metrics),
        3
    );
    state
        .step(
            &store,
            &parameters,
            &Observation::Delete { key: key() },
            &mut metrics,
        )
        .unwrap();
    assert_eq!(
        prediction_for(&mut state, &store, &parameters, query_id(2), &mut metrics),
        4
    );

    assert_eq!(metrics.queries, 3);
    assert_eq!(metrics.payload_reads, 3);
    assert_eq!(metrics.payload_read_bytes, 96);
}

#[test]
fn dense_arm_reads_null_and_every_event_payload() {
    let store = MemoryStore::new(33, 4096).unwrap();
    let parameters = fixture_parameters(Arm::Dense);
    let mut state = State::initialize(&store, &parameters).unwrap();
    let mut metrics = Metrics::default();

    state
        .step(&store, &parameters, &write_class(1), &mut metrics)
        .unwrap();
    prediction_for(&mut state, &store, &parameters, query_id(0), &mut metrics);
    state
        .step(&store, &parameters, &write_class(3), &mut metrics)
        .unwrap();
    prediction_for(&mut state, &store, &parameters, query_id(1), &mut metrics);
    state
        .step(
            &store,
            &parameters,
            &Observation::Delete { key: key() },
            &mut metrics,
        )
        .unwrap();
    prediction_for(&mut state, &store, &parameters, query_id(2), &mut metrics);

    assert_eq!(metrics.payload_reads, 2 + 3 + 4);
    assert_eq!(metrics.payload_read_bytes, 288);
}

#[test]
fn no_history_arm_returns_null_class_and_reads_only_null_payload() {
    let store = MemoryStore::new(33, 4096).unwrap();
    let parameters = fixture_parameters(Arm::NoHistory);
    let mut state = State::initialize(&store, &parameters).unwrap();
    let mut metrics = Metrics::default();

    state
        .step(&store, &parameters, &write_class(1), &mut metrics)
        .unwrap();
    assert_eq!(
        prediction_for(&mut state, &store, &parameters, query_id(0), &mut metrics),
        0
    );
    state
        .step(&store, &parameters, &write_class(3), &mut metrics)
        .unwrap();
    assert_eq!(
        prediction_for(&mut state, &store, &parameters, query_id(1), &mut metrics),
        0
    );
    state
        .step(
            &store,
            &parameters,
            &Observation::Delete { key: key() },
            &mut metrics,
        )
        .unwrap();
    assert_eq!(
        prediction_for(&mut state, &store, &parameters, query_id(2), &mut metrics),
        0
    );

    assert_eq!(metrics.payload_reads, 3);
    assert_eq!(metrics.payload_read_bytes, 96);
}

#[test]
fn invalid_parameters_and_observations_are_rejected_before_state_writes() {
    let parameters = fixture_parameters(Arm::Selective);

    let mut wrong_shape = parameters.clone();
    wrong_shape.query.output_dim = 7;
    assert!(wrong_shape.validate().is_err());

    let mut nonfinite = parameters.clone();
    nonfinite.encoder.weights[0] = f32::NAN;
    assert!(nonfinite.validate().is_err());

    let mut invalid_query_bias = parameters.clone();
    invalid_query_bias.query.bias[0] = 0.25;
    assert_eq!(
        invalid_query_bias.validate().unwrap_err().code,
        "invalid_parameters"
    );

    let store = MemoryStore::new(33, 4096).unwrap();
    let mut state = State::initialize(&store, &parameters).unwrap();
    let mut metrics = Metrics::default();
    assert_eq!(
        state
            .step(
                &store,
                &parameters,
                &Observation::Write {
                    key: vec![1.0; 15],
                    value: 1,
                },
                &mut metrics,
            )
            .unwrap_err()
            .code,
        "invalid_observation"
    );
    assert_eq!(
        state
            .step(
                &store,
                &parameters,
                &Observation::Write {
                    key: key(),
                    value: 4,
                },
                &mut metrics,
            )
            .unwrap_err()
            .code,
        "invalid_observation"
    );
    assert_eq!(state.writes, 0);
    assert_eq!(metrics.writes, 0);
    assert_eq!(
        store
            .begin()
            .unwrap()
            .read_admission(CellRef { id: 1, revision: 1 })
            .unwrap_err()
            .code,
        "stale_reference"
    );
}

#[test]
fn ring_wrap_replaces_first_slot_at_revision_two_after_33_writes() {
    let store = MemoryStore::new(33, 4096).unwrap();
    let parameters = fixture_parameters(Arm::Selective);
    let mut state = State::initialize(&store, &parameters).unwrap();
    let mut metrics = Metrics::default();

    for index in 0..33 {
        state
            .step(
                &store,
                &parameters,
                &write_class(index as usize % 4),
                &mut metrics,
            )
            .unwrap();
    }

    assert_eq!(state.writes, 33);
    assert_eq!(state.cells.len(), 32);
    assert!(state.cells.iter().all(Option::is_some));
    assert_eq!(state.cells[0].as_ref().unwrap().reference.revision, 2);
}
