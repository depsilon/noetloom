"""Bounded EXP-0008 acquisition and diagnostic replay; no final-data entry point."""
from __future__ import annotations

import copy
import math
from pathlib import Path
import random
import sys
import time

from . import coordinates_model as scalar, state_rep_data as data, state_rep_worker as common
from .calibration_records import publish_fit, write
from .contracts import ContractError, read_json
from .input_audit import audit_inputs, require_informative_inputs
from .learning_worker import peak_rss_bytes
from .state_rep_contracts import select_measurement


class Work(common.Work):
    def __init__(self, protocol):
        super().__init__(protocol)
        self.counts["probe_updates"] = 0

    def forward(self, arm, lengths, *, encoded=True):
        self.add("presentations", len(lengths))
        self.add("forward_prefixes", sum(lengths))
        for length in lengths:
            counts = scalar.forward_ops(arm, length)
            initial = scalar.forward_ops(arm, 0)
            for key, value in counts.items():
                self.counts["dense_forward_ops"][key] += value - (initial[key] if not encoded else 0)

    def auxiliary(self, arm, count, mappings=2):
        if arm == "direct":
            return
        self.add("auxiliary_observations", count)
        for key, value in scalar.forward_ops(arm, 0).items():
            self.counts["dense_forward_ops"][key] += count * value * mappings


def backend(protocol):
    common.backend(protocol)
    from . import coordinates_torch
    return coordinates_torch


def audit(protocol):
    raw = data.acquisition_raw(protocol, "mixed")
    dataset = data.generate(protocol, "nonlinear", "mixed")
    prefixes = {split: [{"initial": row["initial"], "actions": row["actions"][:i + 1], "expected": target}
                       for row in rows for i, target in enumerate(row["targets"])] for split, rows in dataset.items()}
    result = audit_inputs(prefixes, data.signature)
    require_informative_inputs(result, disjoint_pairs=("training/validation",))
    config, partitions = protocol["data"], data.partition(protocol["data"])
    seen = {split: {s for initial, word, _ in rows for s in data.path(config, initial, word)} for split, rows in raw.items()}
    for split, states in seen.items():
        if states - set(partitions["training"] + partitions[split]):
            raise ContractError("acquisition path crossed its admitted state partitions")
    all_states = seen["training"] | seen["validation"]
    if len({tuple(data.observe(config, s, "nonlinear")) for s in all_states}) != len(all_states):
        raise ContractError("audited observation mapping is not injective")
    return {"prefix_inputs": result, "seen_states": {k: len(v) for k, v in seen.items()},
            "training_heldout_state_overlap": 0, "observation_injective": True,
            "development_or_final_trajectories_rendered": False,
            "scope": "Ordered initial observations and action prefixes; every auxiliary target audited. No fixed pooling or canonical-state input."}


def scalar_check(runner, rows, count=12):
    chosen = [rows[i * (len(rows) - 1) // max(1, count - 1)] for i in range(min(count, len(rows)))]
    outputs, states = runner.infer(chosen)
    snapshot, maximum, scalars = runner.model.snapshot(0), 0.0, 0
    for row, values, native in zip(chosen, outputs, states):
        runner.work.forward(runner.arm, [len(row["actions"])])
        expected, expected_states = scalar.scalar_forward(snapshot, row["initial"], row["actions"])
        for actual, target in ((values, expected), (native, expected_states)):
            for left, right in zip(actual, target):
                for a, b in zip(left, right):
                    maximum, scalars = max(maximum, abs(a - b)), scalars + 1
                    if not math.isfinite(a) or not math.isfinite(b) or abs(a - b) > 0.0002 * (1 + abs(b)):
                        raise ContractError("coordinate tensor and independent scalar equations disagree")
    return {"cases": len(chosen), "scalars": scalars, "maximum_absolute_error": maximum,
            "tolerance": "2e-4 * (1 + abs(scalar)), float32 versus float64"}


def perturbations(engine, model, rows, rate, protocol, work):
    """Independent local SGD interventions; never mutate the fitted model or optimizer."""
    torch, snapshot = engine.torch, model.snapshot(0)
    before, _ = common.evaluate(common.NativeRunner(engine, model, work), rows)
    result = {"before": before, "groups": {}}
    for group in protocol["diagnostics"]["prediction_perturbation"]["groups"][model.arm]:
        trial = engine.Model.restore(snapshot)
        selected = [p for name, p in trial.named_parameters()
                    if group == "all" or (group == "mappings" and not name.startswith("transition_"))
                    or name.startswith(group + "_")]
        initial = torch.tensor([row["initial"] for row in rows])
        actions = torch.tensor([row["actions"] for row in rows])
        targets = torch.tensor([row["targets"] for row in rows])
        work.forward(trial.arm, [len(row["actions"]) for row in rows])
        loss = (trial(initial, actions) - targets).square().mean()
        work.add("backward_graph_calls", 1)
        loss.backward()
        if not selected or any(p.grad is None or not torch.isfinite(p.grad).all() for p in selected):
            raise ContractError("missing or nonfinite perturbation gradient")
        norm = float(torch.nn.utils.clip_grad_norm_(selected, protocol["training"]["gradient_clip_norm"]))
        if not math.isfinite(norm):
            raise ContractError("nonfinite perturbation gradient norm")
        work.add("updates", 1)
        work.add("probe_updates", 1)
        work.add("parameter_update_elements", sum(p.numel() for p in selected))
        with torch.no_grad():
            for parameter in selected:
                parameter.add_(parameter.grad, alpha=-rate)
        after, _ = common.evaluate(common.NativeRunner(engine, trial, work), rows)
        result["groups"][group] = {"after": after, "gradient_norm_before_clip": norm,
                                   "prediction_mse_delta": after["loss"] - before["loss"],
                                   "reconstruction_mse_delta": after["reconstruction"]["mse"] - before["reconstruction"]["mse"]}
    if model.snapshot(0) != snapshot:
        raise ContractError("diagnostic changed the candidate")
    return result


def rate_for(protocol, condition):
    return next(c["rate"] for c in protocol["conditions"] if c["name"] == condition)


def fit(engine, protocol, request, directory, work):
    start, stage = time.monotonic(), request["stage"]
    write(directory, "fitting-status.json", {"status": "running"})
    if stage == "mixed":
        parent = Path(request["original"])
        selected = read_json(parent / "fit.json")["selected_step"]
        model = engine.Model.restore(read_json(parent / f"parameters-{selected}.json"))
    else:
        model = engine.Model(request["arm"], request["seed"])
    initial_snapshot = model.snapshot(0)
    write(directory, "initial-parameters.json", initial_snapshot)
    dataset = data.generate(protocol, "nonlinear", stage)
    write(directory, "data.json", dataset)
    rate = rate_for(protocol, request["condition"])
    optimizer = engine.torch.optim.Adam(model.parameters(), lr=rate)
    rng = random.Random(request["seed"] + {"tiny": 0, "one": 1, "mixed": 2}[stage])
    buckets = {length: [row for row in dataset["training"] if len(row["actions"]) == length]
               for length in sorted({len(row["actions"]) for row in dataset["training"]})}
    measurements, predictions, probes = [], [], {}
    telemetry = {"updates": 0, "mean": {}, "maximum_gradient_norm": 0.0}
    for step in range(protocol["training"]["steps"][stage] + 1):
        if step in protocol["training"]["measurement_steps"][stage]:
            write(directory, f"parameters-{step}.json", model.snapshot(step))
            measured, outputs = common.measure(common.NativeRunner(engine, model, work), dataset, step)
            measurements.append(measured)
            predictions.append(outputs)
            write(directory, "curve.json", {"measurements": measurements, "telemetry": telemetry})
        if step in protocol["diagnostics"]["prediction_perturbation"]["steps"][stage]:
            probes[str(step)] = perturbations(engine, model, data.generate(protocol, "nonlinear", "tiny")["training"], rate, protocol, work)
            write(directory, "perturbations.json", probes)
        if step == protocol["training"]["steps"][stage]:
            break
        bucket = buckets[rng.choice(list(buckets))]
        values = common.update(engine, model, optimizer, [rng.choice(bucket) for _ in range(8)], protocol, work)
        telemetry["updates"] += 1
        for key, value in values.items():
            old = telemetry["mean"].get(key, 0.0)
            telemetry["mean"][key] = old + (value - old) / telemetry["updates"]
        telemetry["maximum_gradient_norm"] = max(telemetry["maximum_gradient_norm"], values["gradient_norm_before_clip"])
    write(directory, "perturbations.json", probes)
    selected, gate = select_measurement(protocol, stage, measurements)
    chosen = measurements[selected]["step"]
    write(directory, "predictions.json", predictions[selected])
    result = {"stage": stage, "arm": request["arm"], "seed": request["seed"], "condition": request["condition"],
              "measurements": measurements, "selected_index": selected, "selected_step": chosen,
              "acquisition": gate, "completed_updates": telemetry["updates"], "telemetry": telemetry,
              "fitting_seconds": time.monotonic() - start, "parameter_count": scalar.parameter_count(model.arm),
              "fitting_work": copy.deepcopy(work.counts), "snapshot_scope": "Inference parameters; fresh Adam per cohort."}
    def checks():
        runner = common.NativeRunner(engine, engine.Model.restore(read_json(directory / f"parameters-{chosen}.json")), work)
        return {"scalar": scalar_check(runner, dataset["training"] + dataset["validation"]),
                "saved_state": common.persist_check(runner, dataset["training"], directory, "selected-state.json")}
    publish_fit(directory, result, checks)


def verify_fit(engine, protocol, original, directory, work):
    record = read_json(original / "fit.json")
    request = read_json(original / "request.json")
    if any(record[k] != request[k] for k in ("stage", "arm", "condition", "seed")):
        raise ContractError("coordinate fit identity differs from its request")
    stage = record["stage"]
    dataset = read_json(original / "data.json")
    if dataset != data.generate(protocol, "nonlinear", stage):
        raise ContractError("coordinate fitting data differs from the registered generator")
    if [m["step"] for m in record["measurements"]] != protocol["training"]["measurement_steps"][stage]:
        raise ContractError("coordinate curve lacks its complete registered steps")
    if stage == "mixed":
        # Prefer the restored bundle's parent when replaying a private copy.
        parent = original.parent / Path(request["original"]).name
        if not parent.is_dir():
            parent = Path(request["original"])
        parent_step = read_json(parent / "fit.json")["selected_step"]
        initial = read_json(parent / f"parameters-{parent_step}.json")
        initial["step"] = 0
    else:
        initial = engine.Model(record["arm"], record["seed"]).snapshot(0)
    if initial != read_json(original / "initial-parameters.json") or initial != read_json(original / "parameters-0.json"):
        raise ContractError("coordinate initialization differs from its declared seed or parent")
    measured_all, selected_outputs, probes = [], None, {}
    for previous in record["measurements"]:
        step = previous["step"]
        model = engine.Model.restore(read_json(original / f"parameters-{step}.json"))
        if model.arm != record["arm"] or model.seed != record["seed"]:
            raise ContractError("coordinate checkpoint belongs to another arm or seed")
        measured, outputs = common.measure(common.NativeRunner(engine, model, work), dataset, step)
        if measured != previous:
            raise ContractError("saved coordinate measurement differs on replay")
        measured_all.append(measured)
        if step == record["selected_step"]:
            selected_outputs = outputs
        if step in protocol["diagnostics"]["prediction_perturbation"]["steps"][stage]:
            probes[str(step)] = perturbations(engine, model, data.generate(protocol, "nonlinear", "tiny")["training"],
                                              rate_for(protocol, record["condition"]), protocol, work)
    selected, gate = select_measurement(protocol, stage, measured_all)
    if selected != record["selected_index"] or gate != record["acquisition"]:
        raise ContractError("coordinate selection or acquisition gate differs on replay")
    if selected_outputs != read_json(original / "predictions.json") or probes != read_json(original / "perturbations.json"):
        raise ContractError("coordinate predictions or perturbations differ on replay")
    if record["completed_updates"] != protocol["training"]["steps"][stage]:
        raise ContractError("coordinate fit did not complete its declared duration")
    write(directory, "replayed-perturbations.json", probes)
    model = engine.Model.restore(read_json(original / f"parameters-{record['selected_step']}.json"))
    runner = common.NativeRunner(engine, model, work)
    return {"complete_measurement_selection_prediction_perturbation_replay": True,
            "scalar": scalar_check(runner, dataset["training"] + dataset["validation"]),
            "saved_state": common.persist_check(runner, dataset["training"], directory, "selected-state.json")}


def oracle(engine, protocol, directory, work):
    # Deliberately local import: no candidate model can import this diagnostic fixture.
    from .state_rep_oracle import oracle_snapshot
    snapshot = oracle_snapshot(protocol["data"])
    snapshot["schema_version"] = "noetloom.coordinates_parameters.v1"
    model = engine.Model.restore(snapshot)
    write(directory, "oracle-parameters.json", snapshot)
    rows = [data.render(protocol["data"], "nonlinear", initial, word, family)
            for initial, word, family in data.acquisition_raw(protocol, "one")["training"]]
    long_rows = [data.render(protocol["data"], "nonlinear", initial, word, "oracle_training6")
                 for initial, word in data.sample(protocol["data"], "training", data.training_words(protocol["data"], 6),
                                                 64, protocol["diagnostics"]["oracle"]["salt"])]
    write(directory, "oracle-data.json", {"one": rows, "six": long_rows})
    runner, result, outputs = common.NativeRunner(engine, model, work), {}, {}
    for name, values in (("one", rows), ("six", long_rows)):
        result[name], outputs[name] = common.evaluate(runner, values)
        result[name]["scalar"] = scalar_check(runner, values, len(values))
    write(directory, "oracle-outputs.json", outputs)
    result["scope"] = "Constructed 1804-parameter finite-bipolar capacity witness, not a trained result; training states only."
    write(directory, "result.json", result)
    if any(result[name]["scored"]["all"]["all_prefix_exact_accuracy"] != 1.0 for name in ("one", "six")):
        raise ContractError("constructed capacity witness failed its registered training paths")


def preflight(engine, protocol, directory, work, *, injection=False):
    rows, result = common.synthetic(), {}
    if not injection:
        result["input_audit"] = audit(protocol)
    for arm in ["latent"] if injection else protocol["arms"]:
        model = engine.Model(arm, 180897)
        optimizer = engine.torch.optim.Adam(model.parameters(), lr=0.003)
        for _ in range(8 if injection else 16):
            common.update(engine, model, optimizer, rows, protocol, work)
        restored = engine.Model.restore(model.snapshot(16))
        result[arm] = scalar_check(common.NativeRunner(engine, restored, work), rows, 8)
        result[arm]["reconstruction"] = common.evaluate(common.NativeRunner(engine, restored, work), rows)[0]["reconstruction"]
        if sum(p.numel() for p in model.parameters()) != scalar.parameter_count(arm):
            raise ContractError("coordinate parameter count differs")
    if injection:
        publish_fit(directory, {"completed_updates": 8, "scope": "Synthetic failure-boundary test."},
                    lambda: {}, inject_failure=True)
    else:
        write(directory, "result.json", result)


def main():
    directory = Path(sys.argv[1])
    protocol, request = read_json(directory / "protocol.json"), read_json(directory / "request.json")
    work = Work(protocol)
    try:
        engine = backend(protocol)
        kind = request["kind"]
        if kind in {"preflight", "injection"}:
            preflight(engine, protocol, directory, work, injection=kind == "injection")
        elif kind == "fit":
            fit(engine, protocol, request, directory, work)
        elif kind == "oracle":
            oracle(engine, protocol, directory, work)
        elif kind == "replay":
            original = Path(request["original"])
            if read_json(original / "request.json")["kind"] == "fit":
                write(directory, "result.json", verify_fit(engine, protocol, original, directory, work))
            else:
                oracle(engine, protocol, directory, work)
                for name in ("result.json", "oracle-parameters.json", "oracle-data.json", "oracle-outputs.json"):
                    if read_json(directory / name) != read_json(original / name):
                        raise ContractError("capacity-witness replay differs")
        else:
            raise ContractError("unregistered coordinate operation")
        if kind != "fit":
            write(directory, "verification-status.json", {"status": "completed", "scope": "Execution and registered replay only; acquisition is separate."})
    finally:
        write(directory, "work.json", {**work.counts, "scope": "Dense forward arithmetic; backward graphs and parameter updates counted separately. Includes diagnostics and verification, not full FLOPs."})
        write(directory, "worker-resources.json", {"peak_rss_bytes": peak_rss_bytes()})


if __name__ == "__main__":
    main()
