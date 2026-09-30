use noetloom_core::memory::MemoryStore;
use noetloom_core::operator::{Activation, Affine};
use noetloom_core::provider::ExecutionProvider;
use noetloom_core::representation::{Arm, Inputs, Parameters, Sample, transport};
use noetloom_core::store::{Store, StoreLimits};
use noetloom_core::value::{CellRef, Value};
use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

fn layer(input_dim: usize, output_dim: usize, activation: Activation, bias: Vec<f32>) -> Affine {
    Affine {
        input_dim,
        output_dim,
        weights: vec![0.0; input_dim * output_dim],
        bias,
        activation,
    }
}

fn fixture(arm: Arm) -> Parameters {
    let hidden = if arm == Arm::FixedLarge { 160 } else { 32 };
    let intermediate = if matches!(arm, Arm::FixedSmall | Arm::FixedLarge) {
        64
    } else {
        16
    };
    let construction = if arm == Arm::Conditional {
        vec![
            layer(64, 16, Activation::Tanh, vec![0.0; 16]),
            layer(16, 1024, Activation::Identity, vec![0.0; 1024]),
        ]
    } else {
        vec![]
    };
    let mut solver = vec![
        layer(intermediate, hidden, Activation::Tanh, vec![0.0; hidden]),
        layer(hidden, hidden, Activation::Tanh, vec![0.0; hidden]),
        layer(hidden, 2, Activation::Identity, vec![0.0, 0.0]),
    ];
    Parameters {
        schema_version: "noetloom.representation_parameters.v1".into(),
        arm,
        seed: 0,
        step: 0,
        construction,
        static_scores: if arm == Arm::Static {
            vec![0.0; 1024]
        } else {
            vec![]
        },
        solver: {
            // A known output independent of the zero hidden activations.
            solver[2].bias = vec![1.25, -0.75];
            solver
        },
    }
}

fn sample(values: Vec<f32>) -> Sample {
    Sample { values }
}

fn field() -> Vec<f32> {
    (0..64).map(|index| index as f32 / 63.0).collect()
}

#[test]
fn registered_parameter_and_operation_counts_match_python_formulas() {
    let cases = [
        (Arm::FixedSmall, 3202, 6402),
        (Arm::FixedLarge, 36482, 72962),
        (Arm::Conditional, 20114, 46354),
        (Arm::Static, 2690, 10482),
    ];
    let provider = MemoryStore::new(1, 1024 * 1024).unwrap();
    let input = sample(field());
    for (arm, expected_parameters, expected_ops) in cases {
        let parameters = fixture(arm);
        parameters.validate().unwrap();
        assert_eq!(parameters.parameter_count(), expected_parameters);
        let constructed = parameters.construct(&provider, &input).unwrap();
        assert_eq!(
            constructed.nominal_scalar_ops + parameters.solver_ops().unwrap(),
            expected_ops
        );
    }

    let conditional = fixture(Arm::Conditional);
    let constructed = conditional.construct(&provider, &input).unwrap();
    assert!(
        constructed
            .transport
            .as_ref()
            .unwrap()
            .as_chunks::<64>()
            .0
            .iter()
            .all(|row| row.iter().all(|value| (*value - 1.0 / 64.0).abs() < 1e-7))
    );
    assert_eq!(constructed.intermediate.len(), 16);
    for value in &constructed.intermediate {
        assert!((*value - 0.5).abs() < 1e-6);
    }
    assert_eq!(
        conditional
            .solve(&provider, &constructed.intermediate)
            .unwrap(),
        vec![1.25, -0.75]
    );
}

#[test]
fn all_arms_validate_shapes_fixed_fields_pass_through_and_static_transport_is_input_independent() {
    let provider = MemoryStore::new(1, 1024 * 1024).unwrap();
    let first = sample(field());
    let second = sample(vec![-1.0; 64]);
    for arm in [
        Arm::FixedSmall,
        Arm::FixedLarge,
        Arm::Conditional,
        Arm::Static,
    ] {
        let parameters = fixture(arm);
        parameters.validate().unwrap();
        if matches!(arm, Arm::FixedSmall | Arm::FixedLarge) {
            assert_eq!(
                parameters
                    .construct(&provider, &first)
                    .unwrap()
                    .intermediate,
                first.values
            );
            assert_eq!(
                parameters
                    .construct(&provider, &second)
                    .unwrap()
                    .intermediate,
                second.values
            );
        }
    }
    let static_parameters = fixture(Arm::Static);
    let first_constructed = static_parameters.construct(&provider, &first).unwrap();
    let second_constructed = static_parameters.construct(&provider, &second).unwrap();
    assert_eq!(first_constructed.transport, second_constructed.transport);
    assert_ne!(
        first_constructed.intermediate,
        second_constructed.intermediate
    );
}

#[test]
fn invalid_parameter_shapes_activations_static_scores_and_nonfinite_values_are_rejected() {
    let mut bad_constructor_dimensions = fixture(Arm::Conditional);
    bad_constructor_dimensions.construction[0].input_dim = 63;
    assert!(bad_constructor_dimensions.validate().is_err());

    let mut bad_solver_activation = fixture(Arm::FixedSmall);
    bad_solver_activation.solver[0].activation = Activation::Identity;
    assert!(bad_solver_activation.validate().is_err());

    let mut bad_static_length = fixture(Arm::Static);
    bad_static_length.static_scores.pop();
    assert!(bad_static_length.validate().is_err());

    let mut nonfinite_construction = fixture(Arm::Conditional);
    nonfinite_construction.construction[0].weights[0] = f32::NAN;
    assert!(nonfinite_construction.validate().is_err());

    let mut nonfinite_static = fixture(Arm::Static);
    nonfinite_static.static_scores[0] = f32::INFINITY;
    assert!(nonfinite_static.validate().is_err());

    for values in [vec![0.0; 63], vec![f32::NAN; 64], vec![2.01; 64]] {
        assert!(sample(values).validate().is_err());
    }
}

#[test]
fn serde_rejects_label_bearing_inputs_samples_and_unknown_parameter_keys() {
    assert!(serde_json::from_str::<Sample>(r#"{"values":[0.0],"expected":1}"#).is_err());
    assert!(
        serde_json::from_str::<Inputs>(
            r#"{"schema_version":"noetloom.representation_inputs.v1","samples":[],"family":"base"}"#
        )
        .is_err()
    );
    assert!(serde_json::from_str::<Inputs>(
        r#"{"schema_version":"noetloom.representation_inputs.v1","samples":[{"values":[],"label":0}]}"#
    ).is_err());
    let mut artifact = serde_json::to_value(fixture(Arm::FixedSmall)).unwrap();
    artifact["expected"] = serde_json::json!(1);
    assert!(serde_json::from_value::<Parameters>(artifact).is_err());
}

#[test]
fn transport_computes_known_rows_and_rejects_bad_matrices_or_input_shape() {
    let provider = MemoryStore::new(1, 1024 * 1024).unwrap();
    let values: Vec<f32> = (0..64).map(|value| value as f32).collect();
    let mut matrix = vec![0.0; 16 * 64];
    let selected: Vec<usize> = (0..16).map(|row| row * 3 + 1).collect();
    for (row, column) in selected.iter().copied().enumerate() {
        matrix[row * 64 + column] = 1.0;
    }
    assert_eq!(
        transport(&provider, &matrix, &values).unwrap(),
        selected
            .into_iter()
            .map(|index| index as f32)
            .collect::<Vec<_>>()
    );

    let mut negative = matrix.clone();
    negative[0] = -0.1;
    for invalid in [vec![0.0; 1023], negative, vec![0.0; 1024]] {
        assert!(transport(&provider, &invalid, &values).is_err());
    }
    assert!(transport(&provider, &matrix, &values[..63]).is_err());
}

struct OwnedTempDir(PathBuf);

impl OwnedTempDir {
    fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        loop {
            let path = std::env::temp_dir().join(format!(
                "noetloom-representation-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
            match fs::create_dir(&path) {
                Ok(()) => return Self(path),
                Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(error) => panic!("cannot create owned fixture directory: {error}"),
            }
        }
    }
}

impl Drop for OwnedTempDir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn intermediate_survives_persistent_store_reopen_and_solves_identically() {
    let resident = MemoryStore::new(1, 1024 * 1024).unwrap();
    let parameters = fixture(Arm::Conditional);
    let input = sample(field());
    let constructed = parameters.construct(&resident, &input).unwrap();
    let resident_logits = parameters
        .solve(&resident, &constructed.intermediate)
        .unwrap();

    let owned = OwnedTempDir::new();
    let store_path = owned.0.join("persistent-store");
    let store = Store::create(&store_path, StoreLimits::default()).unwrap();
    let mut transaction = store.begin().unwrap();
    let reference = transaction
        .write(
            1,
            None,
            Value::Dense {
                data: constructed.intermediate.clone(),
            },
            4096,
        )
        .unwrap();
    transaction
        .commit_with_validation_limit(StoreLimits::default().max_commit_validation_bytes)
        .unwrap();
    drop(store);

    let reopened = Store::open(&store_path, StoreLimits::default()).unwrap();
    let mut transaction = reopened.begin().unwrap();
    let Value::Dense { data: persisted } = transaction.read(reference).unwrap() else {
        panic!("persisted intermediate should be a dense field");
    };
    assert_eq!(persisted, constructed.intermediate);
    assert_eq!(
        parameters.solve(&reopened, &persisted).unwrap(),
        resident_logits
    );
    assert_eq!(reference, CellRef { id: 1, revision: 1 });
}
