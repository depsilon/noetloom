"""Bounded EXP-0007 fitting and full inference replay; final data has no entry point."""
from __future__ import annotations

import math
from pathlib import Path
import random
import sys
import time

from . import affine_model, state_rep_data as data
from .calibration_records import publish_fit, write
from .contracts import ContractError, read_json
from .learning_worker import peak_rss_bytes
from .state_rep_contracts import select_measurement
from .state_rep_metrics import continuation_metrics, reconstruction_metrics, score
from .state_rep_model import forward_ops, parameter_count, scalar_forward


class Work:
    def __init__(self, protocol):
        self.budget = protocol["budget"]
        self.counts = {key: 0 for key in ("updates", "presentations", "forward_prefixes", "auxiliary_observations",
                                        "affine_fit_examples", "parameter_update_elements", "backward_graph_calls")}
        self.counts["dense_forward_ops"] = {key: 0 for key in ("multiply", "add", "tanh")}

    def add(self, key, amount):
        self.counts[key] += amount
        limit = {"updates": "max_updates_per_run", "presentations": "max_presentations_per_run",
                 "forward_prefixes": "max_forward_prefixes_per_run", "auxiliary_observations": "max_auxiliary_observations_per_run",
                 "affine_fit_examples": "max_affine_fit_examples_per_run"}.get(key)
        if limit and self.counts[key] > self.budget[limit]:
            raise ContractError("state-representation worker budget exhausted: " + key)

    def forward(self, arm, lengths, *, encoded=True):
        self.add("presentations", len(lengths))
        self.add("forward_prefixes", sum(lengths))
        for length in lengths:
            counts = (affine_model.forward_ops(10, length) if arm == "affine" else forward_ops(arm, length))
            if not encoded and arm not in {"direct", "affine"}:
                for key, value in (("multiply", 640), ("add", 650), ("tanh", 32)):
                    counts[key] -= value
            for key, value in counts.items():
                self.counts["dense_forward_ops"][key] += value

    def auxiliary(self, arm, count, mappings=2):
        if arm in {"direct", "affine"}:
            return
        self.add("auxiliary_observations", count)
        for key, value in (("multiply", 640), ("add", 650), ("tanh", 32)):
            self.counts["dense_forward_ops"][key] += count * value * mappings


def backend(protocol):
    from . import state_rep_torch as engine
    torch = engine.torch
    if torch.__version__.split("+")[0] != protocol["training"]["version"]:
        raise ContractError("state-representation tensor version differs")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    return engine


class NativeRunner:
    def __init__(self, engine, model, work):
        self.engine, self.model, self.work, self.arm = engine, model, work, model.arm

    def infer(self, rows, *, zero_initial=False, reverse=False):
        torch, model = self.engine.torch, self.model
        outputs, states = [None] * len(rows), [None] * len(rows)
        self.work.forward(self.arm, [len(row["actions"]) for row in rows])
        with torch.no_grad():
            for length in sorted({len(row["actions"]) for row in rows}):
                indices = [i for i, row in enumerate(rows) if len(row["actions"]) == length]
                initial = torch.tensor([rows[i]["initial"] for i in indices])
                actions = torch.tensor([list(reversed(rows[i]["actions"])) if reverse else rows[i]["actions"] for i in indices])
                values, native = model(initial, actions, return_states=True, zero_initial=zero_initial)
                for index, value, state in zip(indices, values.tolist(), native.tolist()):
                    outputs[index], states[index] = value, state
        return outputs, states

    def reconstruct(self, observations):
        self.work.auxiliary(self.arm, len(observations))
        with self.engine.torch.no_grad():
            return self.model.decode(self.model.encode(self.engine.torch.tensor(observations))).tolist()

    def encode(self, observations):
        self.work.auxiliary(self.arm, len(observations), 1)
        with self.engine.torch.no_grad():
            return self.model.encode(self.engine.torch.tensor(observations)).tolist()

    def resume(self, starts, words):
        self.work.forward(self.arm, [len(word) for word in words], encoded=False)
        outputs = [None] * len(words)
        torch = self.engine.torch
        with torch.no_grad():
            for length in sorted({len(word) for word in words}):
                indices = [i for i, word in enumerate(words) if len(word) == length]
                state = torch.tensor([starts[i] for i in indices])
                actions = torch.tensor([words[i] for i in indices])
                values = []
                for action in actions.unbind(1):
                    value, state = self.model.advance(state, action)
                    values.append(value)
                for index, value in zip(indices, torch.stack(values, 1).tolist()):
                    outputs[index] = value
        return outputs


class AffineRunner:
    arm = "affine"

    def __init__(self, parameters, work):
        self.parameters, self.work = parameters, work

    def infer(self, rows, *, zero_initial=False, reverse=False):
        self.work.forward(self.arm, [len(row["actions"]) for row in rows])
        outputs = [affine_model.rollout(self.parameters, [0.0] * 10 if zero_initial else row["initial"],
                   list(reversed(row["actions"])) if reverse else row["actions"]) for row in rows]
        return outputs, outputs

    def reconstruct(self, observations):
        return observations

    def encode(self, observations):
        return observations

    def resume(self, starts, words):
        self.work.forward(self.arm, [len(word) for word in words], encoded=False)
        return [affine_model.rollout(self.parameters, state, word) for state, word in zip(starts, words)]


def mean_prediction_loss(rows, outputs):
    return sum(sum((a - b) ** 2 for target, value in zip(row["targets"], values)
                   for a, b in zip(target, value)) / (10 * len(row["actions"]))
               for row, values in zip(rows, outputs)) / len(rows)


def evaluate(runner, rows):
    outputs, states = runner.infer(rows)
    observations = [observation for row in rows for observation in [row["initial"], *row["targets"]]]
    recon = runner.reconstruct(observations)
    targets = [target for row in rows for target in row["targets"]]
    encoded = runner.encode(targets)
    native = [state for path in states for state in path]
    consistency = sum((a - b) ** 2 for left, right in zip(native, encoded) for a, b in zip(left, right)) / (10 * len(native))
    if not math.isfinite(consistency):
        raise ContractError("nonfinite latent diagnostic")
    return {"loss": mean_prediction_loss(rows, outputs), "scored": score(rows, outputs),
            "reconstruction": reconstruction_metrics(observations, recon), "consistency_mse": consistency}, outputs


def measure(runner, dataset, step):
    result, outputs = {"step": step}, {}
    for split, rows in dataset.items():
        if rows:
            result[split], outputs[split] = evaluate(runner, rows)
    return result, outputs


def objective(engine, model, batch, protocol, work):
    torch = engine.torch
    initial = torch.tensor([row["initial"] for row in batch])
    actions = torch.tensor([row["actions"] for row in batch])
    targets = torch.tensor([row["targets"] for row in batch])
    work.forward(model.arm, [len(row["actions"]) for row in batch])
    values, states = model(initial, actions, return_states=True)
    prediction = (values - targets).square().mean()
    reconstruction = torch.zeros(())
    consistency = torch.zeros(())
    if model.arm != "direct":
        observed = torch.cat((initial[:, None], targets), dim=1)
        work.auxiliary(model.arm, observed.numel() // 10)
        reconstruction = (model.decode(model.encode(observed)) - observed).square().mean()
        if model.arm == "consistent":
            work.auxiliary(model.arm, targets.numel() // 10, 1)
            # This target branch is a diagnostic reference, not a second gradient path.
            consistency = (states - model.encode(targets).detach()).square().mean()
    loss = prediction + protocol["training"]["reconstruction_weight"] * reconstruction
    loss = loss + protocol["training"]["consistency_weight"][model.arm] * consistency
    if not torch.isfinite(loss):
        raise ContractError("nonfinite training objective")
    return loss, {"prediction": float(prediction.detach()), "reconstruction": float(reconstruction.detach()),
                  "consistency": float(consistency.detach()), "total": float(loss.detach())}


def update(engine, model, optimizer, batch, protocol, work):
    optimizer.zero_grad(set_to_none=True)
    loss, parts = objective(engine, model, batch, protocol, work)
    work.add("backward_graph_calls", 1)
    loss.backward()
    gradients = [p.grad for p in model.parameters() if p.grad is not None]
    if not gradients or any(not engine.torch.isfinite(gradient).all() for gradient in gradients):
        raise ContractError("missing or nonfinite training gradient")
    norm = float(engine.torch.nn.utils.clip_grad_norm_(model.parameters(), protocol["training"]["gradient_clip_norm"]))
    if not math.isfinite(norm):
        raise ContractError("nonfinite aggregate gradient norm")
    work.add("updates", 1)
    work.add("parameter_update_elements", sum(p.numel() for p in model.parameters() if p.grad is not None))
    optimizer.step()
    return {**parts, "gradient_norm_before_clip": norm}


def scalar_check(runner, rows, count=12):
    chosen = [rows[i * (len(rows) - 1) // max(1, count - 1)] for i in range(min(count, len(rows)))]
    outputs, states = runner.infer(chosen)
    snapshot = runner.model.snapshot(0)
    maximum, scalars = 0.0, 0
    for row, values, native in zip(chosen, outputs, states):
        runner.work.forward(runner.arm, [len(row["actions"])])
        expected, expected_states = scalar_forward(snapshot, row["initial"], row["actions"])
        for actual, target in ((values, expected), (native, expected_states)):
            for left, right in zip(actual, target):
                for a, b in zip(left, right):
                    maximum, scalars = max(maximum, abs(a - b)), scalars + 1
                    if abs(a - b) > 0.0002 * (1 + abs(b)):
                        raise ContractError("independent scalar equations disagree with tensor inference")
    return {"cases": len(chosen), "scalars": scalars, "maximum_absolute_error": maximum,
            "tolerance": "2e-4 * (1 + abs(scalar)), float32 tensor versus float64 scalar"}


def persist_check(runner, rows, directory, name):
    chosen = [row for row in rows if len(row["actions"]) > 1][:8]
    if not chosen:
        return {"cases": 0, "scope": "No multi-step trajectory at this stage."}
    outputs, states = runner.infer(chosen)
    records = [{"native_state": native[len(row["actions"]) // 2 - 1],
                "remaining_actions": row["actions"][len(row["actions"]) // 2:]}
               for row, native in zip(chosen, states)]
    write(directory, name, {"records": records, "scope": "Inference state only; no optimizer resume claim."})
    restored = read_json(directory / name)["records"]
    continued = runner.resume([r["native_state"] for r in restored], [r["remaining_actions"] for r in restored])
    expected = [value[len(row["actions"]) // 2:] for row, value in zip(chosen, outputs)]
    if continued != expected:
        raise ContractError("serialized native state changes continued inference")
    return {"cases": len(chosen), "exact_saved_state_continuation": True}


def verify_fit(engine, protocol, directory, work):
    fit = read_json(directory / "fit.json")
    checks = {}
    for stage, record in fit["stages"].items():
        dataset = read_json(directory / (stage + "-data.json"))
        if dataset != data.generate(protocol, fit["observation"], stage):
            raise ContractError("replayed fitting observations differ from registration")
        measurements, output = [], None
        for previous in record["measurements"]:
            model = engine.Model.restore(read_json(directory / f"{stage}-parameters-{previous['step']}.json"))
            runner = NativeRunner(engine, model, work)
            measured, predicted = measure(runner, dataset, previous["step"])
            if measured != previous:
                raise ContractError("full saved acquisition measurement differs on replay")
            measurements.append(measured)
            if previous["step"] == record["selected_step"]:
                output = predicted
        selected, gate = select_measurement(protocol, stage, measurements)
        if selected != record["selected_index"] or gate != record["acquisition"]:
            raise ContractError("checkpoint selection or gate differs on replay")
        if output != read_json(directory / (stage + "-predictions.json")):
            raise ContractError("selected complete predictions differ on replay")
        runner = NativeRunner(engine, engine.Model.restore(read_json(directory / f"{stage}-parameters-{record['selected_step']}.json")), work)
        checks[stage] = {"scalar": scalar_check(runner, dataset["training"] + dataset["validation"]),
                         "saved_state": persist_check(runner, dataset["training"], directory, stage + "-state.json")}
    return checks


def fit(engine, protocol, request, directory, work):
    start = time.monotonic()
    write(directory, "fitting-status.json", {"status": "running"})
    model = engine.Model(request["arm"], request["seed"])
    rate = next(c["rate"] for c in protocol["conditions"] if c["name"] == request["condition"])
    stages = {}
    for stage in ("tiny", "one", "mixed"):
        dataset = data.generate(protocol, request["observation"], stage)
        write(directory, stage + "-data.json", dataset)
        optimizer = engine.torch.optim.Adam(model.parameters(), lr=rate)
        rng = random.Random(request["seed"] + {"tiny": 0, "one": 1, "mixed": 2}[stage])
        buckets = {length: [row for row in dataset["training"] if len(row["actions"]) == length]
                   for length in sorted({len(row["actions"]) for row in dataset["training"]})}
        measurements, predictions = [], []
        telemetry = {"updates": 0, "mean": {}, "maximum_gradient_norm": 0.0}
        for step in range(protocol["training"]["steps"][stage] + 1):
            if step in protocol["training"]["measurement_steps"][stage]:
                write(directory, f"{stage}-parameters-{step}.json", model.snapshot(step))
                measured, outputs = measure(NativeRunner(engine, model, work), dataset, step)
                measurements.append(measured)
                predictions.append(outputs)
                write(directory, stage + "-curve.json", {"measurements": measurements, "telemetry": telemetry})
            if step == protocol["training"]["steps"][stage]:
                break
            bucket = buckets[rng.choice(list(buckets))]
            values = update(engine, model, optimizer, [rng.choice(bucket) for _ in range(8)], protocol, work)
            telemetry["updates"] += 1
            for key, value in values.items():
                old = telemetry["mean"].get(key, 0.0)
                telemetry["mean"][key] = old + (value - old) / telemetry["updates"]
            telemetry["maximum_gradient_norm"] = max(telemetry["maximum_gradient_norm"], values["gradient_norm_before_clip"])
        selected, gate = select_measurement(protocol, stage, measurements)
        chosen = measurements[selected]["step"]
        stages[stage] = {"measurements": measurements, "selected_index": selected, "selected_step": chosen,
                         "acquisition": gate, "telemetry": telemetry}
        write(directory, stage + "-predictions.json", predictions[selected])
        model = engine.Model.restore(read_json(directory / f"{stage}-parameters-{chosen}.json"))
        if not gate["passed"]:
            break
    result = {"observation": request["observation"], "arm": request["arm"], "seed": request["seed"],
              "condition": request["condition"], "stages": stages, "completed_updates": work.counts["updates"],
              "acquisition_passed": len(stages) == 3 and all(row["acquisition"]["passed"] for row in stages.values()),
              "fitting_seconds": time.monotonic() - start, "parameter_count": parameter_count(model.arm),
              "fitting_work": work.counts.copy(), "snapshot_scope": "Inference parameters; each stage starts a fresh optimizer."}
    # Full curve replay is a separate admitted process, avoiding hidden budget doubling here.
    def checks():
        runner = NativeRunner(engine, model, work)
        return {"scalar": scalar_check(runner, dataset["training"] + dataset["validation"]),
                "saved_state": persist_check(runner, dataset["training"], directory, "selected-state.json")}
    publish_fit(directory, result, checks)


def continuation(runner, rows, mode="own"):
    outputs, currents, states = [], [], []
    for history in ("history_a", "history_b"):
        values, native = runner.infer([row[history] for row in rows])
        starts = [path[-1] for path in native]
        currents.append([path[-1] for path in values])
        states.append(starts)
        if mode == "zero_state_after_history":
            starts = [[0.0] * 10 for _ in rows]
        elif mode == "provided_current_observation_reset_diagnostic":
            starts = runner.encode([row["current"] for row in rows])
        elif mode != "own":
            raise ContractError("unknown continuation intervention")
        outputs.append(runner.resume(starts, [row["suffix"] for row in rows]))
    payload = {"outputs_a": outputs[0], "outputs_b": outputs[1], "current_a": currents[0], "current_b": currents[1],
               "states_a": states[0], "states_b": states[1]}
    return {"scored": continuation_metrics(rows, **payload), "intervention": mode}, payload


def transfer(runner, protocol, observation, directory):
    rows, pairs = data.development(protocol, observation), data.continuations(protocol, observation)
    write(directory, "development-data.json", {"rows": rows, "continuations": pairs})
    measured, outputs = evaluate(runner, rows)
    result, payload = {"development": measured, "controls": {}}, {"development": outputs, "controls": {}}
    for mode in ("zero_initial_state", "reverse_actions"):
        values, _ = runner.infer(rows, zero_initial=mode == "zero_initial_state", reverse=mode == "reverse_actions")
        result["controls"][mode], payload["controls"][mode] = score(rows, values), values
    result["continuation"], payload["continuation"] = continuation(runner, pairs)
    for mode in ("zero_state_after_history", "provided_current_observation_reset_diagnostic"):
        result["controls"][mode], payload["controls"][mode] = continuation(runner, pairs, mode)
    result["reverse_order_sensitivity"] = data.audit(protocol, observation)["reverse_order_sensitivity"]
    result["saved_state"] = persist_check(runner, rows, directory, "development-state.json")
    if runner.arm != "affine":
        result["scalar"] = scalar_check(runner, rows)
    write(directory, "outputs.json", payload)
    write(directory, "result.json", result)
    return result


def affine(protocol, request, directory, work):
    start = time.monotonic()
    write(directory, "fitting-status.json", {"status": "running"})
    dataset = data.generate(protocol, request["observation"], "one")
    write(directory, "one-data.json", dataset)
    examples = [{"input": row["initial"], "action": row["actions"][0], "target": row["targets"][0]} for row in dataset["training"]]
    work.add("affine_fit_examples", len(examples))
    parameters, report = affine_model.fit_affine(examples, actions=4)
    write(directory, "parameters.json", parameters)
    fit_result = {"completed_updates": 0, "fitting_seconds": time.monotonic() - start, **report}
    runner = AffineRunner(parameters, work)
    def checks():
        training, predictions = measure(runner, dataset, 0)
        write(directory, "acquisition.json", training)
        write(directory, "one-predictions.json", predictions)
        transfer(runner, protocol, request["observation"], directory)
        return {"observed_affine_fit_and_rollout": "completed"}
    publish_fit(directory, fit_result, checks)


def synthetic():
    rng = random.Random(180799)
    rows = []
    for index in range(8):
        initial = [rng.uniform(-1, 1) for _ in range(10)]
        rows.append({"initial": initial, "actions": [index % 4], "targets": [[x * 0.5 for x in initial]], "family": "synthetic"})
    return rows


def gradient_boundary(engine):
    torch = engine.torch
    predicted, target = torch.ones((2, 10), requires_grad=True), torch.zeros((2, 10), requires_grad=True)
    ((predicted - target.detach()).square().mean()).backward()
    if predicted.grad is None or target.grad is not None:
        raise ContractError("consistency target gradient stop failed")
    # Check the actual shared encoder path as well: targets alone cannot train it.
    model = engine.Model("consistent", 180797)
    observed = torch.ones((2, 10), requires_grad=True)
    state = torch.zeros((2, 10), requires_grad=True)
    (state - model.encode(observed).detach()).square().mean().backward()
    if observed.grad is not None or any(p.grad is not None for p in model.parameters()) or state.grad is None:
        raise ContractError("actual target encoder received consistency gradients")
    return {"predicted_branch_active": True, "target_encoder_branch_stopped": True}


def preflight(engine, protocol, directory, work, *, injection=False):
    rows, checks = synthetic(), {}
    if not injection:
        checks["data_audits"] = {observation: data.audit(protocol, observation) for observation in protocol["observations"]}
        checks["gradient_boundary"] = gradient_boundary(engine)
    for arm in ["latent"] if injection else protocol["arms"]:
        model = engine.Model(arm, 180797)
        optimizer = engine.torch.optim.Adam(model.parameters(), lr=0.003)
        for _ in range(8 if injection else 16):
            update(engine, model, optimizer, rows, protocol, work)
        snapshot = model.snapshot(work.counts["updates"])
        write(directory, arm + "-parameters.json", snapshot)
        checks[arm] = scalar_check(NativeRunner(engine, engine.Model.restore(snapshot), work), rows, 8)
    if injection:
        publish_fit(directory, {"completed_updates": work.counts["updates"], "scope": "Synthetic failure-boundary test."},
                    lambda: {}, inject_failure=True)
    else:
        write(directory, "result.json", checks)
        write(directory, "verification-status.json", {"status": "completed", "scope": "Execution and data validity only, no acquisition claim."})


def replay(engine, protocol, request, directory, work):
    original = Path(request["original"])
    old = read_json(original / "request.json")
    if old["kind"] == "fit":
        # The driver binds every original artifact before this copy; only payloads are copied.
        for file in sorted(original.glob("*.json")):
            if file.name.endswith(("-data.json", "-predictions.json")) or "-parameters-" in file.name or file.name == "fit.json":
                write(directory, file.name, read_json(file))
        checks = verify_fit(engine, protocol, directory, work)
        write(directory, "result.json", {"full_measurement_selection_prediction_replay": checks})
    elif old["kind"] == "affine":
        affine(protocol, old, directory, work)
        for name in ("parameters.json", "acquisition.json", "one-predictions.json", "development-data.json", "outputs.json", "result.json"):
            if read_json(directory / name) != read_json(original / name):
                raise ContractError("affine replay changed " + name)
    elif old["kind"] == "transfer":
        snapshot = read_json(original / "parameters.json")
        write(directory, "parameters.json", snapshot)
        runner = NativeRunner(engine, engine.Model.restore(snapshot), work)
        transfer(runner, protocol, old["observation"], directory)
        for name in ("development-data.json", "outputs.json", "result.json"):
            if read_json(directory / name) != read_json(original / name):
                raise ContractError("transfer replay changed " + name)
    else:
        raise ContractError("unregistered original replay kind")
    write(directory, "verification-status.json", {"status": "completed", "complete_replay": True})


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
        elif kind == "affine":
            affine(protocol, request, directory, work)
        elif kind == "transfer":
            original = Path(request["original"])
            fitted = read_json(original / "fit.json")
            step = fitted["stages"]["mixed"]["selected_step"]
            snapshot = read_json(original / f"mixed-parameters-{step}.json")
            write(directory, "parameters.json", snapshot)
            transfer(NativeRunner(engine, engine.Model.restore(snapshot), work), protocol, request["observation"], directory)
            write(directory, "verification-status.json", {"status": "completed"})
        elif kind == "replay":
            replay(engine, protocol, request, directory, work)
        else:
            raise ContractError("unregistered worker operation")
    finally:
        write(directory, "work.json", {**work.counts, "scope": "Dense forward arithmetic only; backward graphs and parameter updates counted separately, not estimated full FLOPs. Includes verification; affine solve arithmetic is in fit.json."})
        write(directory, "worker-resources.json", {"peak_rss_bytes": peak_rss_bytes()})


if __name__ == "__main__":
    main()
