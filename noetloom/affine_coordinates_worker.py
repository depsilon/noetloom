"""EXP-0009: detached affine identification inside fixed learned reversible maps."""
from __future__ import annotations

import copy
from pathlib import Path
import random
import sys
import time

from . import coordinates_worker as coordinates, state_rep_data as data, state_rep_worker as common
from .calibration_records import publish_fit, write
from .contracts import ContractError, read_json
from .learning_worker import peak_rss_bytes
from .state_rep_contracts import select_measurement
from .state_rep_metrics import score


class Work(coordinates.Work):
    def __init__(self, protocol):
        super().__init__(protocol)
        self.counts.pop("probe_updates")
        self.counts.update(linear_systems=0, fitted_parameter_assignments=0, solver_seconds=0.0)

    def add(self, key, amount):
        super().add(key, amount)
        if key == "linear_systems" and self.counts[key] > self.budget["max_linear_systems_per_run"]:
            raise ContractError("affine-coordinate linear-system budget exhausted")


def solver_rows(protocol):
    rows = data.generate(protocol, "nonlinear", "one")["training"]
    expected = protocol["solver"]
    counts = [sum(row["actions"] == [action] for row in rows) for action in range(4)]
    if len(rows) != expected["training_pairs"] or counts != [expected["per_action_pairs"]] * 4:
        raise ContractError("affine support differs from the registered training pool")
    return rows


def refit(engine, model, rows, protocol, work):
    """Use observed consequences only; publish all maps atomically after checks."""
    from .affine_inner_torch import solve_affine
    torch, config = engine.torch, protocol["solver"]
    if (len(rows) != config["training_pairs"] or any(len(row["actions"]) != 1 or len(row["targets"]) != 1 for row in rows)
            or any(sum(row["actions"] == [action] for row in rows) != config["per_action_pairs"] for action in range(4))):
        raise ContractError("refit requires its full declared one-step support")
    before = {name: parameter.detach().clone() for name, parameter in model.named_parameters()
              if not name.startswith("transition_")}
    work.auxiliary("reversible", 2 * len(rows), mappings=1)
    with torch.no_grad():
        initial = model.encode(torch.tensor([row["initial"] for row in rows], dtype=torch.float32)).double()
        target = model.encode(torch.tensor([row["targets"][0] for row in rows], dtype=torch.float32)).double()
    weights, biases, reports = [], [], []
    for action in range(4):
        indices = [index for index, row in enumerate(rows) if row["actions"] == [action]]
        work.add("affine_fit_examples", len(indices))
        work.add("linear_systems", 1)
        started = time.monotonic()
        try:
            weight, bias, report = solve_affine(initial[indices], target[indices], rcond=config["rcond"],
                                               max_condition=config["maximum_condition"])
        finally:
            work.add("solver_seconds", time.monotonic() - started)
        if report["normal_residual_ratio"] > config["maximum_normal_residual_ratio"]:
            raise ContractError("refit normal-equation residual exceeds registration")
        weights.append(weight)
        biases.append(bias)
        reports.append({"action": action, **report})
    with torch.no_grad():
        model.transition_weight.copy_(torch.stack(weights))
        model.transition_bias.copy_(torch.stack(biases))
    work.add("fitted_parameter_assignments", 440)
    if any(not torch.equal(before[name], parameter) for name, parameter in model.named_parameters() if name in before):
        raise ContractError("affine refit changed the learned coordinate mapping")
    return {"actions": reports, "support_pairs": len(rows), "columns": 11, "outputs": 10,
            "gradient": "Detached solve; coupling tensors unchanged."}


def optimizer_for(engine, model, arm, rate):
    if arm not in {"joint", "refit"}:
        raise ContractError("unknown affine-coordinate optimization arm")
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(arm == "joint" or not name.startswith("transition_"))
        parameter.grad = None
    return engine.torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=rate)


def refit_steps(protocol, stage):
    total, interval = protocol["training"]["steps"][stage], protocol["solver"]["interval"]
    return sorted(set(range(0, total + 1, interval)) | {total})


def parent_path(directory, request):
    saved = Path(request["original"])
    local = directory.parent / saved.name
    return local if local.is_dir() else saved


def initial_snapshot(engine, directory, request):
    if request["stage"] == "one":
        return engine.Model("reversible", request["seed"]).snapshot(0)
    parent = parent_path(directory, request)
    parent_record, parent_request = read_json(parent / "fit.json"), read_json(parent / "request.json")
    if (parent_record["stage"] != "one" or not parent_record["acquisition"]["passed"]
            or any(parent_request[key] != request[key] for key in ("arm", "condition", "seed"))):
        raise ContractError("mixed initialization needs its own acquired one-step parent")
    snapshot = read_json(parent / f"parameters-{parent_record['selected_step']}.json")
    snapshot["step"] = 0
    return snapshot


def fit(engine, protocol, request, directory, work):
    started, stage, arm = time.monotonic(), request["stage"], request["arm"]
    write(directory, "fitting-status.json", {"status": "running"})
    initial = initial_snapshot(engine, directory, request)
    model = engine.Model.restore(initial)
    write(directory, "initial-parameters.json", initial)
    dataset = data.generate(protocol, "nonlinear", stage)
    support = solver_rows(protocol) if arm == "refit" else []
    write(directory, "data.json", dataset)
    write(directory, "solver-data.json", {"rows": support})
    optimizer = optimizer_for(engine, model, arm, coordinates.rate_for(protocol, request["condition"]))
    rng = random.Random(request["seed"] + (1 if stage == "one" else 2))
    buckets = {length: [row for row in dataset["training"] if len(row["actions"]) == length]
               for length in sorted({len(row["actions"]) for row in dataset["training"]})}
    measurements, predictions, refits = [], [], []
    telemetry = {"updates": 0, "mean": {}, "maximum_gradient_norm": 0.0}
    scheduled = refit_steps(protocol, stage) if arm == "refit" else []
    for step in range(protocol["training"]["steps"][stage] + 1):
        if step in scheduled:
            write(directory, "refit-status.json", {"status": "running", "step": step})
            report = refit(engine, model, support, protocol, work)
            write(directory, f"refit-{step}.json", model.snapshot(step))
            refits.append({"step": step, **report})
            write(directory, "refits.json", {"refits": refits})
            write(directory, "refit-status.json", {"status": "completed", "step": step})
            write(directory, "fitting-progress.json", telemetry)
        if step in protocol["training"]["measurement_steps"][stage]:
            write(directory, f"parameters-{step}.json", model.snapshot(step))
            measured, outputs = common.measure(common.NativeRunner(engine, model, work), dataset, step)
            measurements.append(measured)
            predictions.append(outputs)
            write(directory, "curve.json", {"measurements": measurements, "telemetry": telemetry})
        if step == protocol["training"]["steps"][stage]:
            break
        bucket = buckets[rng.choice(list(buckets))]
        values = common.update(engine, model, optimizer, [rng.choice(bucket) for _ in range(8)], protocol, work)
        telemetry["updates"] += 1
        for key, value in values.items():
            old = telemetry["mean"].get(key, 0.0)
            telemetry["mean"][key] = old + (value - old) / telemetry["updates"]
        telemetry["maximum_gradient_norm"] = max(telemetry["maximum_gradient_norm"], values["gradient_norm_before_clip"])
    write(directory, "refits.json", {"refits": refits})
    selected, gate = select_measurement(protocol, stage, measurements)
    chosen = measurements[selected]["step"]
    write(directory, "predictions.json", predictions[selected])
    result = {"stage": stage, "arm": arm, "model_arm": "reversible", "seed": request["seed"],
              "condition": request["condition"], "measurements": measurements, "selected_index": selected,
              "selected_step": chosen, "acquisition": gate, "completed_updates": telemetry["updates"],
              "telemetry": telemetry, "fitting_seconds": time.monotonic() - started, "parameter_count": 1780,
              "gradient_parameter_count": 1780 if arm == "joint" else 1340,
              "refit_steps": [row["step"] for row in refits], "fitting_work": copy.deepcopy(work.counts),
              "snapshot_scope": "Inference parameters and detached-refit snapshots; fresh Adam per stage."}
    def checks():
        runner = common.NativeRunner(engine, engine.Model.restore(read_json(directory / f"parameters-{chosen}.json")), work)
        return {"scalar": coordinates.scalar_check(runner, dataset["training"] + dataset["validation"]),
                "saved_state": common.persist_check(runner, dataset["training"], directory, "selected-state.json")}
    publish_fit(directory, result, checks)


def verify_fit(engine, protocol, original, directory, work):
    record, request = read_json(original / "fit.json"), read_json(original / "request.json")
    if any(record[key] != request[key] for key in ("stage", "arm", "condition", "seed")):
        raise ContractError("affine-coordinate fit identity differs from request")
    stage, arm = record["stage"], record["arm"]
    dataset = data.generate(protocol, "nonlinear", stage)
    if read_json(original / "data.json") != dataset:
        raise ContractError("affine-coordinate data differs from registered observations")
    support = solver_rows(protocol) if arm == "refit" else []
    if read_json(original / "solver-data.json")["rows"] != support:
        raise ContractError("affine-coordinate solver support differs")
    initial = initial_snapshot(engine, original, request)
    if read_json(original / "initial-parameters.json") != initial:
        raise ContractError("affine-coordinate initialization differs")
    first = read_json(original / "parameters-0.json")
    if arm == "refit":
        # Refit zero is checked with every other solve below. Only the coordinate
        # tensors must still equal the seeded/parent initialization before it.
        same_initial = all(first["tensors"][name] == value for name, value in initial["tensors"].items()
                           if not name.startswith("transition_"))
    else:
        same_initial = first == initial
    if not same_initial:
        raise ContractError("affine-coordinate step-zero initialization differs")
    expected_refits = refit_steps(protocol, stage) if arm == "refit" else []
    saved_refits = read_json(original / "refits.json")["refits"]
    try:
        saved_steps = sorted(int(path.stem.removeprefix("refit-")) for path in original.glob("refit-*.json")
                             if path.stem != "refit-status")
    except ValueError as error:
        raise ContractError("affine-coordinate refit filename differs") from error
    if (record["refit_steps"] != expected_refits or [row["step"] for row in saved_refits] != expected_refits
            or saved_steps != expected_refits):
        raise ContractError("affine-coordinate refit coverage differs")
    replayed_refits = []
    for previous in saved_refits:
        step = previous["step"]
        snapshot = read_json(original / f"refit-{step}.json")
        if snapshot["arm"] != "reversible" or snapshot["seed"] != record["seed"] or snapshot["step"] != step:
            raise ContractError("refit snapshot identity differs")
        model = engine.Model.restore(snapshot)
        report = {"step": step, **refit(engine, model, support, protocol, work)}
        if model.snapshot(step) != snapshot or report != previous:
            raise ContractError("affine refit maps or diagnostics differ on replay")
        replayed_refits.append(report)
        if step in protocol["training"]["measurement_steps"][stage] and snapshot != read_json(original / f"parameters-{step}.json"):
            raise ContractError("measurement does not use its current refitted maps")
    if [row["step"] for row in record["measurements"]] != protocol["training"]["measurement_steps"][stage]:
        raise ContractError("affine-coordinate measurement coverage differs")
    measured_all, selected_outputs = [], None
    for previous in record["measurements"]:
        step = previous["step"]
        snapshot = read_json(original / f"parameters-{step}.json")
        if snapshot["arm"] != "reversible" or snapshot["seed"] != record["seed"] or snapshot["step"] != step:
            raise ContractError("affine-coordinate checkpoint identity differs")
        measured, outputs = common.measure(common.NativeRunner(engine, engine.Model.restore(snapshot), work), dataset, step)
        if measured != previous:
            raise ContractError("affine-coordinate measurement differs on replay")
        measured_all.append(measured)
        if step == record["selected_step"]:
            selected_outputs = outputs
    selected, gate = select_measurement(protocol, stage, measured_all)
    if (selected != record["selected_index"] or gate != record["acquisition"]
            or record["selected_step"] != measured_all[selected]["step"]
            or selected_outputs != read_json(original / "predictions.json")):
        raise ContractError("affine-coordinate selection, gates or predictions differ on replay")
    if record["completed_updates"] != protocol["training"]["steps"][stage]:
        raise ContractError("affine-coordinate fitting duration differs")
    write(directory, "replayed-refits.json", {"refits": replayed_refits})
    model = engine.Model.restore(read_json(original / f"parameters-{record['selected_step']}.json"))
    runner = common.NativeRunner(engine, model, work)
    return {"complete_measurement_selection_prediction_refit_replay": True, "refits_replayed": len(saved_refits),
            "scalar": coordinates.scalar_check(runner, dataset["training"] + dataset["validation"]),
            "saved_state": common.persist_check(runner, dataset["training"], directory, "selected-state.json")}


def evaluate_model(engine, protocol, model, directory, work):
    runner = common.NativeRunner(engine, model, work)
    rows, pairs = data.development(protocol, "nonlinear"), data.continuations(protocol, "nonlinear")
    write(directory, "development-data.json", {"rows": rows, "continuations": pairs})
    measured, outputs = common.evaluate(runner, rows)
    result, payload = {"development": measured, "controls": {}}, {"development": outputs, "controls": {}}
    for mode in ("zero_initial_state", "reverse_actions"):
        values, _ = runner.infer(rows, zero_initial=mode == "zero_initial_state", reverse=mode == "reverse_actions")
        result["controls"][mode], payload["controls"][mode] = score(rows, values), values
    result["continuation"], payload["continuation"] = common.continuation(runner, pairs)
    for mode in ("zero_state_after_history", "provided_current_observation_reset_diagnostic"):
        result["controls"][mode], payload["controls"][mode] = common.continuation(runner, pairs, mode)
    result["reverse_order_sensitivity"] = data.audit(protocol, "nonlinear")["reverse_order_sensitivity"]
    result["saved_state"] = common.persist_check(runner, rows, directory, "development-state.json")
    result["scalar"] = coordinates.scalar_check(runner, rows)
    limits = protocol["evaluation"]["thresholds"]
    result["competence"] = {"checks": {
        "development/all": measured["scored"]["all"]["all_prefix_exact_accuracy"] >= limits["development_all_prefix_accuracy"],
        **{"development/" + name: row["all_prefix_exact_accuracy"] >= limits["minimum_family_all_prefix_accuracy"]
           for name, row in measured["scored"].items() if name.startswith("family/")},
        "continuation/both": result["continuation"]["scored"]["all"]["both_suffix_accuracy"] >= limits["continuation_both_correct"]}}
    result["competence"]["passed"] = all(result["competence"]["checks"].values())
    write(directory, "outputs.json", payload)
    write(directory, "result.json", result)
    return result


def evaluate(engine, protocol, request, directory, work):
    original = Path(request["original"])
    record = read_json(original / "fit.json")
    if record["stage"] != "mixed" or not record["acquisition"]["passed"]:
        raise ContractError("development needs an acquired mixed checkpoint")
    snapshot = read_json(original / f"parameters-{record['selected_step']}.json")
    write(directory, "parameters.json", snapshot)
    return evaluate_model(engine, protocol, engine.Model.restore(snapshot), directory, work)


def synthetic():
    """Execution fixture only: full-rank observed inputs and simple noisy affine targets."""
    basis = [[0.0] * 10] + [[0.75 * sign if coordinate == axis else 0.0 for coordinate in range(10)]
                            for axis in range(10) for sign in (-1, 1)]
    return [{"initial": initial, "actions": [action], "family": "synthetic",
             "targets": [[initial[(j + action + 1) % 10] * (-1 if (j + action) % 3 == 0 else 1)
                          + 0.03 * (action - j) + 0.04 * initial[(j + 2) % 10] ** 2 for j in range(10)]]}
            for action in range(4) for initial in basis]


def preflight(engine, protocol, directory, work, *, injection=False):
    rows, result = synthetic(), {}
    if not injection:
        result["input_audit"] = coordinates.audit(protocol)
    synthetic_protocol = copy.deepcopy(protocol)
    synthetic_protocol["solver"].update(training_pairs=84, per_action_pairs=21)
    for arm in ("joint",) if injection else protocol["arms"]:
        model = engine.Model("reversible", 180997)
        optimizer = optimizer_for(engine, model, arm, 0.003)
        if arm == "refit":
            refit(engine, model, rows, synthetic_protocol, work)
        transitions = model.transition_weight.detach().clone(), model.transition_bias.detach().clone()
        for _ in range(8 if injection else 16):
            common.update(engine, model, optimizer, rows[:8], protocol, work)
        if arm == "refit":
            if not engine.torch.equal(transitions[0], model.transition_weight) or not engine.torch.equal(transitions[1], model.transition_bias):
                raise ContractError("refit-arm Adam changed fixed transitions")
            refit(engine, model, rows, synthetic_protocol, work)
        runner = common.NativeRunner(engine, engine.Model.restore(model.snapshot(16)), work)
        result[arm] = coordinates.scalar_check(runner, rows, 12)
        result[arm]["reconstruction"] = common.evaluate(runner, rows)[0]["reconstruction"]
    if injection:
        publish_fit(directory, {"completed_updates": 8, "scope": "Synthetic post-fit failure boundary."},
                    lambda: {}, inject_failure=True)
    else:
        write(directory, "result.json", result)


def main():
    directory = Path(sys.argv[1])
    protocol, request = read_json(directory / "protocol.json"), read_json(directory / "request.json")
    work = Work(protocol)
    try:
        engine = coordinates.backend(protocol)
        kind = request["kind"]
        if kind in {"preflight", "injection"}:
            preflight(engine, protocol, directory, work, injection=kind == "injection")
        elif kind == "fit":
            fit(engine, protocol, request, directory, work)
        elif kind == "evaluate":
            evaluate(engine, protocol, request, directory, work)
        elif kind == "replay":
            original = Path(request["original"])
            original_request = read_json(original / "request.json")
            if original_request["kind"] == "fit":
                write(directory, "result.json", verify_fit(engine, protocol, original, directory, work))
            else:
                snapshot = read_json(original / "parameters.json")
                parent = parent_path(original, original_request)
                parent_record = read_json(parent / "fit.json")
                expected = read_json(parent / f"parameters-{parent_record['selected_step']}.json")
                if (parent_record["stage"] != "mixed" or not parent_record["acquisition"]["passed"]
                        or snapshot != expected):
                    raise ContractError("development replay does not use its acquired parent")
                evaluate_model(engine, protocol, engine.Model.restore(snapshot), directory, work)
                for name in ("development-data.json", "outputs.json", "result.json"):
                    if read_json(directory / name) != read_json(original / name):
                        raise ContractError("affine-coordinate development replay differs")
        else:
            raise ContractError("unregistered affine-coordinate operation")
        if kind != "fit":
            write(directory, "verification-status.json", {"status": "completed", "scope": "Execution/replay only; acquisition and competence have separate gates."})
    finally:
        write(directory, "work.json", {**work.counts, "scope": "Model dense forward arithmetic; backward calls, gradient parameters, fitted assignments and linear systems are separate. Solver SVD and backward arithmetic are not complete FLOP estimates."})
        write(directory, "worker-resources.json", {"peak_rss_bytes": peak_rss_bytes()})


if __name__ == "__main__":
    main()
