"""EXP-0010: adapt observation mappings while retaining or refitting acquired operations."""
from __future__ import annotations

import copy
import math
from pathlib import Path
import random
import sys
import time

from . import affine_coordinates_worker as affine, coordinates_worker as coordinates
from . import representation_bridge_data as data, state_rep_data as old_data, state_rep_worker as common
from .calibration_records import publish_fit, write
from .contracts import ContractError, read_json
from .coordinates_model import validate_snapshot
from .learning_worker import peak_rss_bytes
from .representation_bridge_contracts import frozen, operation_digest, parent_spec, select_measurement, warm
from .state_rep_metrics import score
from .storage import file_digest


class Work(affine.Work):
    def __init__(self, protocol):
        super().__init__(protocol)
        self.counts.update(view_vectors=0, view_multiply=0, view_add=0, frozen_operation_checks=0)


def parent_path(directory, request):
    saved = Path(request["original"])
    local = directory.parent / saved.name
    parent = local if local.is_dir() else saved
    if file_digest(parent / "manifest.json") != request["original_manifest_sha256"]:
        raise ContractError("bridge parent differs from its bound manifest")
    return parent


def retained_snapshot(protocol, seed, directory, request=None):
    """Embed the exact old parameters; restored replay needs no live old cache."""
    spec = parent_spec(protocol, seed)
    path = directory / "retained-parameters.json"
    if not path.is_file():
        if request is None or not request.get("retained_parent"):
            raise ContractError("bridge run lacks its embedded retained parameters")
        source = Path(request["retained_parent"])
        if (source.name != spec["run"] or file_digest(source / "manifest.json") != spec["manifest_sha256"]
                or request.get("retained_parent_manifest_sha256") != spec["manifest_sha256"]
                or file_digest(source / spec["snapshot"]) != spec["snapshot_sha256"]):
            raise ContractError("retained parent or selected snapshot differs")
        write(directory, path.name, read_json(source / spec["snapshot"]))
    if file_digest(path) != spec["snapshot_sha256"]:
        raise ContractError("embedded retained parameters differ from registration")
    snapshot = read_json(path)
    validate_snapshot(snapshot)
    if snapshot["arm"] != "reversible" or snapshot["seed"] != spec["parent_seed"]:
        raise ContractError("retained model identity differs")
    return snapshot


def initial_snapshot(engine, protocol, directory, request):
    retained = retained_snapshot(protocol, request["seed"], directory, request)
    if request["stage"] == "mixed":
        parent = parent_path(directory, request)
        previous, old_request = read_json(parent / "fit.json"), read_json(parent / "request.json")
        if (previous["stage"] != "one" or not previous["acquisition"]["passed"]
                or any(old_request[key] != request[key] for key in ("observation", "arm", "condition", "seed"))
                or retained_snapshot(protocol, request["seed"], parent) != retained):
            raise ContractError("mixed bridge initialization needs its own acquired one-step parent")
        snapshot = read_json(parent / f"parameters-{previous['selected_step']}.json")
        snapshot["step"] = 0
        return snapshot
    snapshot = engine.Model("reversible", request["seed"]).snapshot(0)
    for name in snapshot["tensors"]:
        operation = name.startswith("transition_")
        if (operation and frozen(request["arm"])) or (not operation and warm(request["arm"])):
            snapshot["tensors"][name] = copy.deepcopy(retained["tensors"][name])
    return snapshot


def expected_operations(engine, retained):
    return (engine.torch.tensor(retained["tensors"]["transition_weight"], dtype=engine.torch.float32),
            engine.torch.tensor(retained["tensors"]["transition_bias"], dtype=engine.torch.float32))


def check_operations(engine, model, expected, work):
    work.add("frozen_operation_checks", 1)
    if (not engine.torch.equal(model.transition_weight, expected[0])
            or not engine.torch.equal(model.transition_bias, expected[1])):
        raise ContractError("frozen bridge operations changed")


def solver_rows(protocol, observation, work):
    rows = data.generate(protocol, observation, "one", work)["training"]
    expected = protocol["solver"]
    counts = [sum(row["actions"] == [action] for row in rows) for action in range(4)]
    if len(rows) != expected["training_pairs"] or counts != [expected["per_action_pairs"]] * 4:
        raise ContractError("bridge affine support differs from registered training observations")
    return rows


def fit(engine, protocol, request, directory, work):
    started = time.monotonic()
    stage, arm, observation = request["stage"], request["arm"], request["observation"]
    is_frozen = frozen(arm)
    write(directory, "fitting-status.json", {"status": "running"})
    initial = initial_snapshot(engine, protocol, directory, request)
    retained = retained_snapshot(protocol, request["seed"], directory)
    model = engine.Model.restore(initial)
    write(directory, "initial-parameters.json", initial)
    expected = expected_operations(engine, retained)
    if is_frozen:
        check_operations(engine, model, expected, work)
    dataset = data.generate(protocol, observation, stage, work)
    support = [] if is_frozen else solver_rows(protocol, observation, work)
    write(directory, "data.json", dataset)
    write(directory, "solver-data.json", {"rows": support})
    # Both treatments optimize only coupling parameters. Refit uses detached
    # assignments between updates; frozen operations are checked after each one.
    optimizer = affine.optimizer_for(engine, model, "refit", coordinates.rate_for(protocol, request["condition"]))
    rng = random.Random(request["seed"] + (1 if stage == "one" else 2))
    buckets = {length: [row for row in dataset["training"] if len(row["actions"]) == length]
               for length in sorted({len(row["actions"]) for row in dataset["training"]})}
    measurements, predictions, refits, measurement_work = [], [], [], []
    telemetry = {"updates": 0, "mean": {}, "maximum_gradient_norm": 0.0}
    scheduled = [] if is_frozen else affine.refit_steps(protocol, stage)
    for step in range(protocol["training"]["steps"][stage] + 1):
        if step in scheduled:
            write(directory, "refit-status.json", {"status": "running", "step": step})
            report = affine.refit(engine, model, support, protocol, work)
            write(directory, f"refit-{step}.json", model.snapshot(step))
            refits.append({"step": step, **report})
            write(directory, "refits.json", {"refits": refits})
            write(directory, "refit-status.json", {"status": "completed", "step": step})
            write(directory, "fitting-progress.json", telemetry)
        if step in protocol["training"]["measurement_steps"][stage]:
            snapshot = model.snapshot(step)
            write(directory, f"parameters-{step}.json", snapshot)
            measured, outputs = common.measure(common.NativeRunner(engine, model, work), dataset, step)
            measurements.append(measured)
            predictions.append(outputs)
            measurement_work.append({"step": step, "usage": copy.deepcopy(work.counts),
                                     "seconds_since_fit_start": time.monotonic() - started})
            write(directory, "curve.json", {"measurements": measurements, "telemetry": telemetry,
                                           "measurement_work": measurement_work})
        if step == protocol["training"]["steps"][stage]:
            break
        bucket = buckets[rng.choice(list(buckets))]
        values = common.update(engine, model, optimizer, [rng.choice(bucket) for _ in range(8)], protocol, work)
        if is_frozen:
            check_operations(engine, model, expected, work)
        telemetry["updates"] += 1
        for name, value in values.items():
            old = telemetry["mean"].get(name, 0.0)
            telemetry["mean"][name] = old + (value - old) / telemetry["updates"]
        telemetry["maximum_gradient_norm"] = max(telemetry["maximum_gradient_norm"], values["gradient_norm_before_clip"])
    write(directory, "refits.json", {"refits": refits})
    selected, gate = select_measurement(protocol, stage, measurements)
    chosen = measurements[selected]["step"]
    snapshot = read_json(directory / f"parameters-{chosen}.json")
    write(directory, "predictions.json", predictions[selected])
    result = {"stage": stage, "arm": arm, "observation": observation, "model_arm": "reversible", "seed": request["seed"],
              "condition": request["condition"], "measurements": measurements, "selected_index": selected,
              "selected_step": chosen, "acquisition": gate, "completed_updates": telemetry["updates"],
              "telemetry": telemetry, "fitting_seconds": time.monotonic() - started, "parameter_count": 1780,
              "gradient_parameter_count": 1340, "refit_steps": [row["step"] for row in refits],
              "measurement_work": measurement_work, "fitting_work": copy.deepcopy(work.counts),
              "retained_parameter_sha256": file_digest(directory / "retained-parameters.json"),
              "retained_operation_sha256": operation_digest(retained), "selected_operation_sha256": operation_digest(snapshot),
              "frozen_operations": is_frozen, "frozen_operation_checks": work.counts["frozen_operation_checks"],
              "snapshot_scope": "Inference parameters; old version immutable, fresh Adam per stage. No exact optimizer resume."}
    def checks():
        if is_frozen and result["selected_operation_sha256"] != result["retained_operation_sha256"]:
            raise ContractError("selected bridge snapshot changed retained operations")
        runner = common.NativeRunner(engine, engine.Model.restore(snapshot), work)
        return {"scalar": coordinates.scalar_check(runner, dataset["training"] + dataset["validation"]),
                "saved_state": common.persist_check(runner, dataset["training"], directory, "selected-state.json")}
    publish_fit(directory, result, checks)


def verify_measurement_work(record, protocol):
    steps = protocol["training"]["measurement_steps"][record["stage"]]
    points = record["measurement_work"]
    if [point["step"] for point in points] != steps:
        raise ContractError("bridge acquisition-point work coverage differs")
    previous, elapsed = {}, -1.0
    for point in points:
        usage, step, seconds = point["usage"], point["step"], point["seconds_since_fit_start"]
        if (usage.get("updates") != step or usage.get("backward_graph_calls") != step
                or usage.get("parameter_update_elements") != 1340 * step
                or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < elapsed):
            raise ContractError("bridge acquisition-point update or time accounting differs")
        flat = {key: value for key, value in usage.items() if type(value) in (int, float)}
        flat.update({"dense/" + key: value for key, value in usage["dense_forward_ops"].items()})
        for key, value in flat.items():
            if not math.isfinite(value) or value < previous.get(key, 0):
                raise ContractError("bridge acquisition-point work is not finite and monotonic")
        previous, elapsed = flat, seconds


def verify_fit(engine, protocol, original, directory, work):
    record, request = read_json(original / "fit.json"), read_json(original / "request.json")
    if any(record[key] != request[key] for key in ("stage", "observation", "arm", "condition", "seed")):
        raise ContractError("bridge fit identity differs from request")
    stage, arm, observation = record["stage"], record["arm"], record["observation"]
    is_frozen = frozen(arm)
    retained = retained_snapshot(protocol, record["seed"], original)
    dataset = data.generate(protocol, observation, stage, work)
    support = [] if is_frozen else solver_rows(protocol, observation, work)
    if read_json(original / "data.json") != dataset or read_json(original / "solver-data.json")["rows"] != support:
        raise ContractError("bridge data or affine support differs from registered observations")
    initial = initial_snapshot(engine, protocol, original, request)
    if read_json(original / "initial-parameters.json") != initial:
        raise ContractError("bridge initialization differs")
    first = read_json(original / "parameters-0.json")
    same_initial = first == initial if is_frozen else all(
        first["tensors"][name] == value for name, value in initial["tensors"].items() if not name.startswith("transition_"))
    if not same_initial:
        raise ContractError("bridge step-zero initialization differs")
    expected_refits = [] if is_frozen else affine.refit_steps(protocol, stage)
    saved_refits = read_json(original / "refits.json")["refits"]
    try:
        saved_steps = sorted(int(path.stem.removeprefix("refit-")) for path in original.glob("refit-*.json")
                             if path.stem != "refit-status")
    except ValueError as error:
        raise ContractError("bridge refit filename differs") from error
    if (record["refit_steps"] != expected_refits or [row["step"] for row in saved_refits] != expected_refits
            or saved_steps != expected_refits):
        raise ContractError("bridge refit coverage differs")
    replayed_refits = []
    for previous in saved_refits:
        step = previous["step"]
        snapshot = read_json(original / f"refit-{step}.json")
        if snapshot["arm"] != "reversible" or snapshot["seed"] != record["seed"] or snapshot["step"] != step:
            raise ContractError("bridge refit snapshot identity differs")
        model = engine.Model.restore(snapshot)
        report = {"step": step, **affine.refit(engine, model, support, protocol, work)}
        if model.snapshot(step) != snapshot or report != previous:
            raise ContractError("bridge affine maps or diagnostics differ on replay")
        replayed_refits.append(report)
        if step in protocol["training"]["measurement_steps"][stage] and snapshot != read_json(original / f"parameters-{step}.json"):
            raise ContractError("bridge measurement does not use its current refitted maps")
    if [row["step"] for row in record["measurements"]] != protocol["training"]["measurement_steps"][stage]:
        raise ContractError("bridge measurement coverage differs")
    measured_all, selected_outputs = [], None
    old_digest = operation_digest(retained)
    for previous in record["measurements"]:
        step = previous["step"]
        snapshot = read_json(original / f"parameters-{step}.json")
        if snapshot["arm"] != "reversible" or snapshot["seed"] != record["seed"] or snapshot["step"] != step:
            raise ContractError("bridge checkpoint identity differs")
        if is_frozen and operation_digest(snapshot) != old_digest:
            raise ContractError("bridge checkpoint changed frozen operations")
        model = engine.Model.restore(snapshot)
        if is_frozen:
            check_operations(engine, model, expected_operations(engine, retained), work)
        measured, outputs = common.measure(common.NativeRunner(engine, model, work), dataset, step)
        if measured != previous:
            raise ContractError("bridge measurement differs on replay")
        measured_all.append(measured)
        if step == record["selected_step"]:
            selected_outputs = outputs
    selected, gate = select_measurement(protocol, stage, measured_all)
    if (selected != record["selected_index"] or gate != record["acquisition"]
            or record["selected_step"] != measured_all[selected]["step"]
            or selected_outputs != read_json(original / "predictions.json")):
        raise ContractError("bridge selection, gates or predictions differ on replay")
    if (record["completed_updates"] != protocol["training"]["steps"][stage]
            or record["frozen_operation_checks"] != (record["completed_updates"] + 1 if is_frozen else 0)
            or record["retained_parameter_sha256"] != file_digest(original / "retained-parameters.json")
            or record["retained_operation_sha256"] != old_digest or record["frozen_operations"] != is_frozen):
        raise ContractError("bridge fitting duration, freezing checks or retained identity differs")
    verify_measurement_work(record, protocol)
    write(directory, "replayed-refits.json", {"refits": replayed_refits})
    snapshot = read_json(original / f"parameters-{record['selected_step']}.json")
    if record["selected_operation_sha256"] != operation_digest(snapshot):
        raise ContractError("bridge selected operation identity differs")
    runner = common.NativeRunner(engine, engine.Model.restore(snapshot), work)
    return {"complete_measurement_selection_prediction_refit_replay": True, "refits_replayed": len(saved_refits),
            "retained_parameter_sha256": record["retained_parameter_sha256"], "frozen_operations": is_frozen,
            "historical_work_scope": "Update counts, monotonicity and source-bound telemetry checked; historical timing is not remeasured.",
            "scalar": coordinates.scalar_check(runner, dataset["training"] + dataset["validation"]),
            "saved_state": common.persist_check(runner, dataset["training"], directory, "selected-state.json")}


def evaluate_model(engine, protocol, model, observation, directory, work, label):
    runner = common.NativeRunner(engine, model, work)
    rows = data.development(protocol, observation, work)
    pairs = data.continuations(protocol, observation, work)
    write(directory, label + "-development-data.json", {"rows": rows, "continuations": pairs})
    measured, outputs = common.evaluate(runner, rows)
    result, payload = {"development": measured, "controls": {}}, {"development": outputs, "controls": {}}
    for mode in ("zero_initial_state", "reverse_actions"):
        values, _ = runner.infer(rows, zero_initial=mode == "zero_initial_state", reverse=mode == "reverse_actions")
        result["controls"][mode], payload["controls"][mode] = score(rows, values), values
    result["continuation"], payload["continuation"] = common.continuation(runner, pairs)
    for mode in ("zero_state_after_history", "provided_current_observation_reset_diagnostic"):
        result["controls"][mode], payload["controls"][mode] = common.continuation(runner, pairs, mode)
    result["reverse_order_sensitivity"] = old_data.audit(protocol, "nonlinear")["reverse_order_sensitivity"]
    result["saved_state"] = common.persist_check(runner, rows, directory, label + "-state.json")
    result["scalar"] = coordinates.scalar_check(runner, rows)
    limits = protocol["evaluation"]["thresholds"]
    result["competence"] = {"checks": {
        "development/all": measured["scored"]["all"]["all_prefix_exact_accuracy"] >= limits["development_all_prefix_accuracy"],
        **{"development/" + name: row["all_prefix_exact_accuracy"] >= limits["minimum_family_all_prefix_accuracy"]
           for name, row in measured["scored"].items() if name.startswith("family/")},
        "continuation/both": result["continuation"]["scored"]["all"]["both_suffix_accuracy"] >= limits["continuation_both_correct"]}}
    result["competence"]["passed"] = all(result["competence"]["checks"].values())
    write(directory, label + "-outputs.json", payload)
    write(directory, label + "-result.json", result)
    return result


def baseline(engine, protocol, request, directory, work):
    retained = retained_snapshot(protocol, request["seed"], directory, request)
    model = engine.Model.restore(retained)
    old = evaluate_model(engine, protocol, model, "old", directory, work, "old")
    measurements, datasets, outputs = {}, {}, {}
    for observation in protocol["observations"]:
        datasets[observation] = data.generate(protocol, observation, "one", work)
        measurements[observation], outputs[observation] = common.measure(
            common.NativeRunner(engine, model, work), datasets[observation], 0)
    if model.snapshot(retained["step"]) != retained:
        raise ContractError("baseline changed the retained model")
    retained_snapshot(protocol, request["seed"], directory)
    result = {"seed": request["seed"], "old_competence": old["competence"], "old": old,
              "new_one": measurements, "retained_parameter_sha256": file_digest(directory / "retained-parameters.json"),
              "retained_operation_sha256": operation_digest(retained)}
    write(directory, "zero-shot-data.json", datasets)
    write(directory, "zero-shot-outputs.json", outputs)
    write(directory, "result.json", result)
    return result


def evaluate(engine, protocol, request, directory, work):
    original = Path(request["original"])
    if file_digest(original / "manifest.json") != request["original_manifest_sha256"]:
        raise ContractError("development parent differs from its bound manifest")
    record, fit_request = read_json(original / "fit.json"), read_json(original / "request.json")
    if (record["stage"] != "mixed" or not record["acquisition"]["passed"]
            or fit_request["kind"] != "fit"
            or any(record[key] != fit_request[key] for key in ("stage", "observation", "arm", "condition", "seed"))):
        raise ContractError("development needs an acquired mixed checkpoint with the same identity")
    retained = retained_snapshot(protocol, record["seed"], original)
    write(directory, "retained-parameters.json", retained)
    retained_snapshot(protocol, record["seed"], directory)
    snapshot = read_json(original / f"parameters-{record['selected_step']}.json")
    if snapshot["seed"] != record["seed"] or snapshot["step"] != record["selected_step"]:
        raise ContractError("development selected snapshot identity differs")
    if frozen(record["arm"]) and operation_digest(snapshot) != operation_digest(retained):
        raise ContractError("development snapshot changed the frozen operations")
    write(directory, "parameters.json", snapshot)
    identity = {key: record[key] for key in ("observation", "arm", "condition", "seed", "selected_step")}
    identity.update(retained_parameter_sha256=file_digest(directory / "retained-parameters.json"),
                    retained_operation_sha256=operation_digest(retained),
                    selected_operation_sha256=operation_digest(snapshot))
    write(directory, "evaluation-identity.json", identity)
    result = evaluate_model(engine, protocol, engine.Model.restore(snapshot), record["observation"], directory, work, "new")
    result = {**result, "identity": identity}
    write(directory, "result.json", result)
    return result


def preflight(engine, protocol, directory, work, *, injection=False):
    rows, result = affine.synthetic(), {}
    if not injection:
        result["input_audit"] = data.audit(protocol, work)
    synthetic_protocol = copy.deepcopy(protocol)
    synthetic_protocol["solver"].update(training_pairs=84, per_action_pairs=21)
    retained = engine.Model("reversible", 180991).snapshot(0)
    for arm in ("frozen_reset",) if injection else protocol["arms"]:
        model = engine.Model("reversible", 180997)
        initial = model.snapshot(0)
        for name in initial["tensors"]:
            operation = name.startswith("transition_")
            if (operation and frozen(arm)) or (not operation and warm(arm)):
                initial["tensors"][name] = copy.deepcopy(retained["tensors"][name])
        model = engine.Model.restore(initial)
        expected = expected_operations(engine, retained)
        optimizer = affine.optimizer_for(engine, model, "refit", 0.01)
        if frozen(arm):
            check_operations(engine, model, expected, work)
        else:
            affine.refit(engine, model, rows, synthetic_protocol, work)
        for _ in range(8 if injection else 16):
            common.update(engine, model, optimizer, rows[:8], protocol, work)
            if frozen(arm):
                check_operations(engine, model, expected, work)
        if not frozen(arm):
            affine.refit(engine, model, rows, synthetic_protocol, work)
        runner = common.NativeRunner(engine, engine.Model.restore(model.snapshot(16)), work)
        result[arm] = coordinates.scalar_check(runner, rows, 12)
        result[arm]["reconstruction"] = common.evaluate(runner, rows)[0]["reconstruction"]
    if injection:
        publish_fit(directory, {"completed_updates": 8, "scope": "Synthetic post-fit failure boundary."},
                    lambda: {}, inject_failure=True)
    else:
        write(directory, "result.json", result)


def replay(engine, protocol, request, directory, work):
    original = Path(request["original"])
    if file_digest(original / "manifest.json") != request["original_manifest_sha256"]:
        raise ContractError("replay original differs from its bound manifest")
    original_request = read_json(original / "request.json")
    kind = original_request["kind"]
    if kind == "fit":
        write(directory, "result.json", verify_fit(engine, protocol, original, directory, work))
        return
    if kind == "baseline":
        retained = retained_snapshot(protocol, original_request["seed"], original)
        write(directory, "retained-parameters.json", retained)
        baseline(engine, protocol, original_request, directory, work)
        names = ("old-development-data.json", "old-outputs.json", "old-result.json", "old-state.json",
                 "zero-shot-data.json", "zero-shot-outputs.json", "result.json", "retained-parameters.json")
    elif kind == "evaluate":
        restored_request = {**original_request, "original": str(parent_path(original, original_request))}
        evaluate(engine, protocol, restored_request, directory, work)
        names = ("new-development-data.json", "new-outputs.json", "new-result.json", "new-state.json", "result.json",
                 "parameters.json", "retained-parameters.json", "evaluation-identity.json")
    else:
        raise ContractError("unregistered bridge replay kind")
    if any(read_json(directory / name) != read_json(original / name) for name in names):
        raise ContractError("bridge baseline or development replay differs")


def main():
    directory = Path(sys.argv[1])
    protocol, request = read_json(directory / "protocol.json"), read_json(directory / "request.json")
    work = Work(protocol)
    try:
        engine = coordinates.backend(protocol)
        kind = request["kind"]
        if kind in {"preflight", "injection"}:
            preflight(engine, protocol, directory, work, injection=kind == "injection")
        elif kind == "baseline":
            baseline(engine, protocol, request, directory, work)
        elif kind == "fit":
            fit(engine, protocol, request, directory, work)
        elif kind == "evaluate":
            evaluate(engine, protocol, request, directory, work)
        elif kind == "replay":
            replay(engine, protocol, request, directory, work)
        else:
            raise ContractError("unregistered representation-bridge operation")
        if kind != "fit":
            write(directory, "verification-status.json", {"status": "completed", "scope": "Execution/replay only; acquisition and competence have separate gates."})
    finally:
        write(directory, "work.json", {**work.counts, "scope": "Model dense forward arithmetic; backward calls, gradient parameters, fitted assignments and linear systems are separate. View vectors and multiply/add counts belong to benchmark generation. Solver SVD and backward arithmetic are not complete FLOP estimates."})
        write(directory, "worker-resources.json", {"peak_rss_bytes": peak_rss_bytes()})


if __name__ == "__main__":
    main()
