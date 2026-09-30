use noetloom_core::learning::{
    AllocationGate, Arm, Metrics, Observation, Parameters, State, allocation_features,
};
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
        gate: None,
    }
}

fn adaptive_parameters(bias: f32) -> Parameters {
    let mut parameters = fixture_parameters(Arm::Adaptive);
    parameters.schema_version = "noetloom.cell_parameters.v2".into();
    parameters.gate = Some(AllocationGate {
        weights: vec![0.0; 6],
        bias,
    });
    parameters
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

#[test]
fn adaptive_always_halt_matches_frozen_selective_and_reads_one_payload() {
    let adaptive_store = MemoryStore::new(33, 4096).unwrap();
    let selective_store = MemoryStore::new(33, 4096).unwrap();
    let adaptive = adaptive_parameters(-10.0);
    let selective = fixture_parameters(Arm::Selective);
    let mut adaptive_state = State::initialize(&adaptive_store, &adaptive).unwrap();
    let mut selective_state = State::initialize(&selective_store, &selective).unwrap();
    let mut adaptive_metrics = Metrics::default();
    let mut selective_metrics = Metrics::default();
    for value in [1, 3] {
        adaptive_state
            .step(
                &adaptive_store,
                &adaptive,
                &write_class(value),
                &mut adaptive_metrics,
            )
            .unwrap();
        selective_state
            .step(
                &selective_store,
                &selective,
                &write_class(value),
                &mut selective_metrics,
            )
            .unwrap();
    }

    let adaptive_prediction = adaptive_state
        .step(
            &adaptive_store,
            &adaptive,
            &query_id(0),
            &mut adaptive_metrics,
        )
        .unwrap()
        .unwrap();
    let selective_prediction = selective_state
        .step(
            &selective_store,
            &selective,
            &query_id(0),
            &mut selective_metrics,
        )
        .unwrap()
        .unwrap();
    assert_eq!(adaptive_prediction.logits, selective_prediction.logits);
    assert_eq!(adaptive_prediction.selected, selective_prediction.selected);
    assert_eq!(adaptive_prediction.continued, Some(false));
    assert_eq!(adaptive_metrics.payload_reads, 1);
    assert_eq!(adaptive_metrics.gate_queries, 1);
    assert_eq!(adaptive_metrics.continued_queries, 0);
}

#[test]
fn adaptive_always_continue_matches_dense_without_rereading_first_payload() {
    let adaptive_store = MemoryStore::new(33, 4096).unwrap();
    let dense_store = MemoryStore::new(33, 4096).unwrap();
    let adaptive = adaptive_parameters(10.0);
    let dense = fixture_parameters(Arm::Dense);
    let mut adaptive_state = State::initialize(&adaptive_store, &adaptive).unwrap();
    let mut dense_state = State::initialize(&dense_store, &dense).unwrap();
    let mut adaptive_metrics = Metrics::default();
    let mut dense_metrics = Metrics::default();
    for value in [1, 3] {
        adaptive_state
            .step(
                &adaptive_store,
                &adaptive,
                &write_class(value),
                &mut adaptive_metrics,
            )
            .unwrap();
        dense_state
            .step(
                &dense_store,
                &dense,
                &write_class(value),
                &mut dense_metrics,
            )
            .unwrap();
    }

    let adaptive_prediction = adaptive_state
        .step(
            &adaptive_store,
            &adaptive,
            &query_id(0),
            &mut adaptive_metrics,
        )
        .unwrap()
        .unwrap();
    let dense_prediction = dense_state
        .step(&dense_store, &dense, &query_id(0), &mut dense_metrics)
        .unwrap()
        .unwrap();
    for (actual, expected) in adaptive_prediction
        .logits
        .iter()
        .zip(&dense_prediction.logits)
    {
        assert!((actual - expected).abs() < 1e-6);
    }
    assert_eq!(adaptive_prediction.selected, None);
    assert_eq!(adaptive_prediction.continued, Some(true));
    assert_eq!(adaptive_metrics.payload_reads, 3); // two live cells + null; first read is reused
    assert_eq!(adaptive_metrics.payload_reads, dense_metrics.payload_reads);
    assert_eq!(adaptive_metrics.continued_queries, 1);
    assert!(adaptive_metrics.gate_nominal_scalar_ops > 0);
}

#[test]
fn adaptive_zero_score_continues_and_tied_routing_keeps_first_cell() {
    let store = MemoryStore::new(33, 4096).unwrap();
    let adaptive = adaptive_parameters(0.0);
    let mut state = State::initialize(&store, &adaptive).unwrap();
    let mut metrics = Metrics::default();
    state
        .step(&store, &adaptive, &write_class(1), &mut metrics)
        .unwrap();
    let prediction = state
        .step(&store, &adaptive, &query_id(0), &mut metrics)
        .unwrap()
        .unwrap();
    assert_eq!(prediction.gate_score, Some(0.0));
    assert_eq!(prediction.continued, Some(true));
    assert_eq!(prediction.selected, None);

    let tied_store = MemoryStore::new(33, 4096).unwrap();
    let mut halt = adaptive_parameters(-1.0);
    halt.age_coefficient = 0.0;
    let mut tied_state = State::initialize(&tied_store, &halt).unwrap();
    let mut tied_metrics = Metrics::default();
    tied_state
        .step(&tied_store, &halt, &write_class(1), &mut tied_metrics)
        .unwrap();
    tied_state
        .step(&tied_store, &halt, &write_class(1), &mut tied_metrics)
        .unwrap();
    let expected_first = tied_state.cells[0].as_ref().unwrap().reference;
    let tied = tied_state
        .step(&tied_store, &halt, &query_id(0), &mut tied_metrics)
        .unwrap()
        .unwrap();
    assert_eq!(tied.selected, Some(expected_first));
}

#[test]
fn adaptive_parameters_reject_schema_gate_and_nonfinite_combinations() {
    let valid = adaptive_parameters(0.0);
    valid.validate().unwrap();

    let mut missing_gate = valid.clone();
    missing_gate.gate = None;
    assert!(missing_gate.validate().is_err());
    let mut wrong_version = valid.clone();
    wrong_version.schema_version = "noetloom.cell_parameters.v1".into();
    assert!(wrong_version.validate().is_err());
    let mut wrong_arm = valid.clone();
    wrong_arm.arm = Arm::Dense;
    assert!(wrong_arm.validate().is_err());
    let mut bad_dimensions = valid.clone();
    bad_dimensions.gate.as_mut().unwrap().weights.pop();
    assert!(bad_dimensions.validate().is_err());
    let mut nonfinite_weight = valid.clone();
    nonfinite_weight.gate.as_mut().unwrap().weights[2] = f32::NAN;
    assert!(nonfinite_weight.validate().is_err());
    let mut nonfinite_bias = valid;
    nonfinite_bias.gate.as_mut().unwrap().bias = f32::INFINITY;
    assert!(nonfinite_bias.validate().is_err());
}

#[test]
fn allocation_features_match_uniform_and_single_null_probabilities() {
    let uniform = allocation_features(&[0.2; 5], &[0.0; 5]).unwrap();
    assert!((uniform[0] - 0.2).abs() < 1e-6);
    assert!(uniform[1].abs() < 1e-6);
    assert!((uniform[2] - 1.0).abs() < 1e-6);
    assert!((uniform[3] - 0.2).abs() < 1e-6);
    assert!(uniform[4].abs() < 1e-6);
    assert!((uniform[5] - 4.0 / 32.0).abs() < 1e-6);

    let single_null = allocation_features(&[1.0], &[0.0, 0.0, 0.0, 0.0, 0.0]).unwrap();
    assert_eq!(single_null, vec![1.0, 1.0, 0.0, 0.2, 0.0, 0.0]);
}

#[test]
fn allocation_features_reject_malformed_weights_and_logits() {
    for (weights, logits) in [
        (vec![], vec![0.0; 5]),
        (vec![0.5, 0.6], vec![0.0; 5]),
        (vec![f32::NAN], vec![0.0; 5]),
        (vec![1.0], vec![0.0; 4]),
        (vec![1.0], vec![f32::INFINITY; 5]),
    ] {
        assert!(allocation_features(&weights, &logits).is_err());
    }
}
