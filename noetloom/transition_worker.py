"""Serialized optional numerical worker for EXP-0006."""
from __future__ import annotations

import math
from pathlib import Path
import platform
import random
import sys
import time

from .calibration_records import publish_fit, write
from .contracts import ContractError, read_json
from .learning_worker import peak_rss_bytes
from .storage import file_digest
from .transition_contracts import select_measurement
from .transition_data import audit, generate, score, simulate, transfer
from .transition_model import forward_ops, parameter_count, scalar_forward


class Work:
    def __init__(self):
        self.updates = self.presentations = self.prefix_predictions = self.forward_proxy_ops = 0

    def charge(self, arm: str, rows: list[dict], copies: int = 1):
        self.presentations += copies * len(rows)
        self.prefix_predictions += copies * sum(len(row["actions"]) for row in rows)
        self.forward_proxy_ops += copies * sum(sum(forward_ops(arm, len(row["actions"])).values()) for row in rows)

    def record(self) -> dict:
        return dict(vars(self))


def backend(protocol: dict):
    from . import transition_torch as engine
    torch = engine.torch
    if torch.__version__.split("+")[0] != protocol["training"]["version"]:
        raise ContractError("transition numerical backend version differs")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    return engine


def tensors(engine, rows: list[dict]):
    # Targets cross only the loss/scorer boundary; forward receives initial+actions.
    return (engine.torch.tensor([row["initial"] for row in rows], dtype=engine.torch.float32),
            engine.torch.tensor([row["actions"] for row in rows], dtype=engine.torch.long),
            engine.torch.tensor([row["targets"] for row in rows], dtype=engine.torch.float32))


def evaluate(engine, model, rows: list[dict], work: Work) -> dict:
    if not rows:
        return {"loss": None, "scored": {}, "predictions": [], "logits": []}
    logits = [None] * len(rows)
    total = 0.0
    for length in sorted({len(row["actions"]) for row in rows}):
        indices = [i for i, row in enumerate(rows) if len(row["actions"]) == length]
        selected = [rows[i] for i in indices]
        initial, actions, targets = tensors(engine, selected)
        with engine.torch.no_grad():
            values = model(initial, actions)
            loss = engine.F.binary_cross_entropy_with_logits(values, targets).item()
        if not math.isfinite(loss):
            raise ContractError("nonfinite transition evaluation")
        total += loss * len(indices)
        for i, value in zip(indices, values.tolist()):
            logits[i] = value
    predictions = [[int(value >= 0) for value in trajectory[-1]] for trajectory in logits]
    work.charge(model.arm, rows)
    return {"loss": total / len(rows), "scored": score(rows, predictions), "predictions": predictions, "logits": logits}


def metrics(result: dict) -> dict:
    return {key: result[key] for key in ("loss", "scored")}


def reference_check(engine, model, rows: list[dict], work: Work) -> dict:
    indices = sorted({round(i * (len(rows) - 1) / 11) for i in range(12)})
    selected = [rows[i] for i in indices]
    snapshot, maximum = model.snapshot(0), 0.0
    for row in selected:
        initial, actions, _ = tensors(engine, [row])
        with engine.torch.no_grad():
            logits, states = model(initial, actions, return_states=True)
        expected, native = scalar_forward(snapshot, row["initial"], row["actions"])
        for actual, reference in zip(logits[0].tolist() + states[0].tolist(), expected + native):
            maximum = max(maximum, *(abs(a - b) for a, b in zip(actual, reference)))
        if [[int(x >= 0) for x in values] for values in logits[0].tolist()] != [[int(x >= 0) for x in values] for values in expected]:
            raise ContractError("scalar/tensor transition bits differ")
    work.charge(model.arm, selected, 2)
    if maximum > 2e-4:
        raise ContractError("scalar/tensor transition parity failed")
    return {"cases": len(selected), "maximum_absolute_error": maximum, "tolerance": 2e-4}


def persist_states(engine, model, rows: list[dict], directory: Path, work: Work, *, filename: str = "inference-state.json") -> dict:
    # Deliberately select complete trajectories at every available length.
    chosen = [next(row for row in rows if len(row["actions"]) == length)
              for length in sorted({len(row["actions"]) for row in rows})]
    saved = []
    for row in chosen:
        initial, actions, _ = tensors(engine, [row])
        with engine.torch.no_grad():
            logits, states = model(initial, actions, return_states=True)
        split = max(1, len(row["actions"]) // 2)
        saved.append({"row": row, "after_actions": split, "state": states[0, split - 1].tolist(),
                      "suffix_logits": logits[0, split:].tolist()})
    write(directory, filename, {"arm": model.arm, "states": saved,
          "scope": "Native learned inference state only; no optimizer or exact training continuation claim."})
    work.charge(model.arm, chosen)
    return restart_states(engine, model, directory, work, filename=filename)


def restart_states(engine, model, directory: Path, work: Work, *, filename: str = "inference-state.json") -> dict:
    saved, maximum, transitions = read_json(directory / filename), 0.0, 0
    if saved["arm"] != model.arm:
        raise ContractError("saved inference-state arm differs")
    for item in saved["states"]:
        state = engine.torch.tensor([item["state"]], dtype=engine.torch.float32)
        suffix = item["row"]["actions"][item["after_actions"]:]
        with engine.torch.no_grad():
            for action, expected in zip(suffix, item["suffix_logits"]):
                logits, state = model.advance(state, engine.torch.tensor([action]))
                maximum = max(maximum, *(abs(a - b) for a, b in zip(logits[0].tolist(), expected)))
                transitions += 1
        if len(suffix) != len(item["suffix_logits"]):
            raise ContractError("persisted continuation length differs")
        if suffix:
            work.charge(model.arm, [{"actions": suffix}])
    if maximum > 2e-6:
        raise ContractError("restored learned inference state differs")
    return {"trajectories": len(saved["states"]), "continued_transitions": transitions, "maximum_absolute_error": maximum}


def controls(engine, model, rows: list[dict], initial_snapshot: dict, protocol: dict, work: Work) -> dict:
    reversed_rows = [{**row, "actions": list(reversed(row["actions"]))} for row in rows]
    # Charge two exact-control case visits and each simulator transition, separately
    # from the model's arithmetic proxy. Copy is one eight-bit output per case.
    work.presentations += 2 * len(rows)
    work.prefix_predictions += len(rows) + sum(len(row["actions"]) for row in rows)
    return {"copy_initial": score(rows, [row["initial"] for row in rows]),
            "sorted_exact_simulator": score(rows, [simulate(protocol["data"], row["initial"], sorted(row["actions"]))[-1] for row in rows]),
            "untrained": evaluate(engine, engine.Model.restore(initial_snapshot), rows, work),
            "reversed_actions": evaluate(engine, model, reversed_rows, work),
            "scope": "Exact sorted simulator is a labeled order-insensitive oracle control, never part of learned inference. Reversed actions are scored against the original ordered target."}


def verify_selected(engine, model, data: dict, fit: dict, protocol: dict, request: dict, directory: Path, work: Work) -> dict:
    predictions = {name: evaluate(engine, model, rows, work) for name, rows in data.items()}
    selected = fit["measurements"][fit["selected_measurement"]]
    for name in ("training", "validation"):
        if metrics(predictions[name]) != selected[name]:
            raise ContractError("selected transition snapshot does not reproduce fit metrics")
    write(directory, "predictions.json", predictions)
    reference = reference_check(engine, model, data["training"] + data["validation"], work)
    restart = persist_states(engine, model, data["training"] + data["validation"], directory, work)
    return {"reference": reference, "restart": restart, "acquisition": fit["acquisition"]}


def train(engine, protocol: dict, request: dict, directory: Path, work: Work) -> None:
    model = engine.Model(request["arm"], request["seed"])
    condition = next(c for c in protocol["conditions"] if c["name"] == request["condition"])
    steps = 8 if request["kind"] == "injection" else protocol["training"]["steps"][request["stage"]]
    data = generate(protocol, request["stage"])
    write(directory, "data.json", data)
    buckets = {length: [row for row in data["training"] if len(row["actions"]) == length]
               for length in sorted({len(row["actions"]) for row in data["training"]})}
    prepared = {length: tensors(engine, rows) for length, rows in buckets.items()}
    opt = engine.torch.optim.Adam(model.parameters(), lr=condition["learning_rate"], betas=(0.9, 0.999),
                                 eps=1e-8, weight_decay=0.0, foreach=False, fused=False)
    rng = random.Random(request["seed"] ^ 231117)
    lengths, weights = list(buckets), [len(rows) for rows in buckets.values()]
    measure_at = {round(steps * fraction) for fraction in protocol["training"]["measurement_fractions"]}
    measurements, losses, lengths_used = [], [], []
    started = time.monotonic()
    write(directory, "fitting-status.json", {"status": "running", "completed_updates": 0})
    for step in range(steps + 1):
        if step:
            length = rng.choices(lengths, weights=weights)[0]
            x, a, y = prepared[length]
            indices = [rng.randrange(len(x)) for _ in range(protocol["training"]["batch_size"])]
            opt.zero_grad(set_to_none=True)
            loss = engine.F.binary_cross_entropy_with_logits(model(x[indices], a[indices]), y[indices])
            if not engine.torch.isfinite(loss):
                raise ContractError("nonfinite transition training loss")
            loss.backward()
            engine.torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
            opt.step()
            losses.append(loss.item())
            lengths_used.append(length)
            work.updates += 1
            work.charge(model.arm, [buckets[length][i] for i in indices])
        if step in measure_at:
            name = f"parameters-{step}.json"
            write(directory, name, model.snapshot(step))
            measurements.append({"step": step, "elapsed_seconds": time.monotonic() - started,
                                 "training": metrics(evaluate(engine, model, data["training"], work)),
                                 "validation": metrics(evaluate(engine, model, data["validation"], work)),
                                 "snapshot": name, "snapshot_sha256": file_digest(directory / name)})
            write(directory, "fit-progress.json", {"completed_updates": step, "losses": losses,
                                                    "batch_lengths": lengths_used, "measurements": measurements})
    index, acquisition = select_measurement(request["stage"], measurements, protocol)
    snapshot = read_json(directory / measurements[index]["snapshot"])
    write(directory, "selected.json", snapshot)
    training_forward = sum(16 * sum(forward_ops(model.arm, length).values()) for length in lengths_used)
    fit = {"schema_version": "noetloom.transitions_fit.v1", "identity": request,
           "data_sha256": file_digest(directory / "data.json"), "protocol_sha256": file_digest(directory / "protocol.json"),
           "completed_updates": steps, "fitting_work": work.record(), "fitting_seconds": time.monotonic() - started,
           "worker_peak_rss_bytes": peak_rss_bytes(), "parameter_count": parameter_count(model.arm),
           "training_proxy_ops": 3 * training_forward + 10 * steps * parameter_count(model.arm),
           "cost_scope": "Forward arithmetic proxy plus 2x forward for backward and 10 operations/parameter/update for Adam; measured wall/RSS separately. Evaluation and scalar/restart work also charged.",
           "losses": losses, "batch_lengths": lengths_used, "measurements": measurements,
           "selected_measurement": index, "selected_sha256": file_digest(directory / "selected.json"), "acquisition": acquisition}
    publish_fit(directory, fit, lambda: verify_selected(engine, engine.Model.restore(snapshot), data, fit, protocol, request, directory, work),
                inject_failure=request["kind"] == "injection")


def replay(engine, protocol: dict, request: dict, directory: Path, work: Work) -> None:
    original = Path(request["original"])
    original_request = read_json(original / "request.json")
    if original_request["kind"] == "replay":
        replay_transfer(engine, protocol, request, directory, work)
        return
    fit, data = read_json(original / "fit.json"), read_json(original / "data.json", 8 * 1024**2)
    old = read_json(original / "request.json")
    steps = protocol["training"]["steps"][old["stage"]]
    schedule = [round(steps * fraction) for fraction in protocol["training"]["measurement_fractions"]]
    if (fit["identity"] != old or fit["completed_updates"] != steps or len(fit["losses"]) != steps
            or len(fit["batch_lengths"]) != steps or [row["step"] for row in fit["measurements"]] != schedule
            or fit["data_sha256"] != file_digest(original / "data.json")
            or fit["protocol_sha256"] != file_digest(original / "protocol.json")
            or data != generate(protocol, old["stage"])):
        raise ContractError("transition fit identity, data or measurement schedule differs")
    for measurement in fit["measurements"]:
        path = original / measurement["snapshot"]
        snapshot = read_json(path)
        if (file_digest(path) != measurement["snapshot_sha256"]
                or (snapshot["arm"], snapshot["seed"], snapshot["step"]) != (old["arm"], old["seed"], measurement["step"])):
            raise ContractError("transition measurement snapshot differs")
        model = engine.Model.restore(snapshot)
        for name in ("training", "validation"):
            if metrics(evaluate(engine, model, data[name], work)) != measurement[name]:
                raise ContractError("replayed transition fitting curve differs")
    index, acquisition = select_measurement(old["stage"], fit["measurements"], protocol)
    snapshot = read_json(original / "selected.json")
    if (fit["selected_measurement"] != index or fit["acquisition"] != acquisition
            or snapshot != read_json(original / fit["measurements"][index]["snapshot"])
            or fit["selected_sha256"] != file_digest(original / "selected.json")):
        raise ContractError("transition checkpoint selection differs")
    model = engine.Model.restore(snapshot)
    verification = verify_selected(engine, model, data, fit, protocol, old, directory, work)
    if read_json(directory / "predictions.json", 8 * 1024**2) != read_json(original / "predictions.json", 8 * 1024**2):
        raise ContractError("replayed transition predictions differ")
    if read_json(directory / "inference-state.json") != read_json(original / "inference-state.json"):
        raise ContractError("persisted learned state differs from fresh inference")
    restart = restart_states(engine, model, original, work)
    if request.get("development_transfer"):
        rows = transfer(protocol, "development")
        write(directory, "transfer-data.json", {"rows": rows})
        write(directory, "transfer.json", evaluate(engine, model, rows, work))
        write(directory, "controls.json", controls(engine, model, rows, read_json(original / "parameters-0.json"), protocol, work))
        verification["transfer_reference"] = reference_check(engine, model, rows, work)
        verification["transfer_restart"] = persist_states(engine, model, rows, directory, work, filename="transfer-state.json")
    write(directory, "replay.json", {"status": "passed", "original_fit_sha256": file_digest(original / "fit.json"),
                                    "measurements": len(fit["measurements"]), "restart": restart, "verification": verification,
                                    "development_transfer": bool(request.get("development_transfer")),
                                    "scope": "Fresh parameter, fitted-curve, prediction and native-state inference replay; optimization was not rerun."})


def replay_transfer(engine, protocol: dict, request: dict, directory: Path, work: Work) -> None:
    original = Path(request["original"])
    old = read_json(original / "request.json")
    if old["kind"] != "replay" or not old["development_transfer"] or request.get("development_transfer"):
        raise ContractError("unsupported nested transition replay")
    # Resolve siblings so archived bundles are replayable without original cache bytes.
    parent = original.parent / Path(old["original"]).name
    if file_digest(parent / "manifest.json") != old["original_manifest_sha256"]:
        raise ContractError("transfer replay parent differs")
    rows = transfer(protocol, "development")
    if read_json(original / "transfer-data.json")["rows"] != rows:
        raise ContractError("saved transfer trajectories differ")
    model = engine.Model.restore(read_json(parent / "selected.json"))
    results = evaluate(engine, model, rows, work)
    if results != read_json(original / "transfer.json", 8 * 1024**2):
        raise ContractError("saved transfer predictions or scores differ")
    diagnostic = controls(engine, model, rows, read_json(parent / "parameters-0.json"), protocol, work)
    if diagnostic != read_json(original / "controls.json", 8 * 1024**2):
        raise ContractError("saved transfer control predictions or scores differ")
    restart = persist_states(engine, model, rows, directory, work, filename="transfer-state.json")
    if read_json(directory / "transfer-state.json") != read_json(original / "transfer-state.json"):
        raise ContractError("saved transfer native state differs")
    restart_states(engine, model, original, work, filename="transfer-state.json")
    write(directory, "replay.json", {"status": "passed", "transfer_cases": len(rows), "control_cases": 4 * len(rows),
          "original_manifest_sha256": file_digest(original / "manifest.json"), "restart": restart,
          "reference": reference_check(engine, model, rows, work),
          "scope": "Full fresh replay of saved transfer outcomes, all four controls and learned-state continuation; optimization not rerun."})


def preflight(engine, protocol: dict, directory: Path, work: Work) -> None:
    write(directory, "input-audit.json", audit(protocol))
    torch, report = engine.torch, {}
    rng = random.Random(78111)
    rows = [{"initial": [rng.randrange(2) for _ in range(8)], "actions": [rng.randrange(4) for _ in range(3)],
             "targets": [[rng.randrange(2) for _ in range(8)] for _ in range(3)]} for _ in range(16)]
    x, a, y = tensors(engine, rows)
    for arm in protocol["arms"]:
        model = engine.Model(arm, 9803)
        opt = torch.optim.Adam(model.parameters(), lr=0.003, foreach=False, fused=False)
        timings = []
        for step in range(24):
            start = time.monotonic()
            opt.zero_grad(set_to_none=True)
            loss = engine.F.binary_cross_entropy_with_logits(model(x, a), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
            opt.step()
            work.updates += 1
            work.charge(arm, rows)
            if step >= 8:
                timings.append(time.monotonic() - start)
        projected = sum(timings) / len(timings) * 2048
        if projected > 70:
            raise ContractError("transition duration exceeds preflight throughput margin")
        report[arm] = {"parameter_count": parameter_count(arm), "projected_2048_updates_seconds": projected,
                       "forward_scalar_ops_by_length": {str(length): forward_ops(arm, length) for length in (1, 3, 6)},
                       "reference": reference_check(engine, model, rows, work), "timed_updates": 16, "warmup_updates": 8}
    write(directory, "preflight.json", {"arms": report, "scope": "Synthetic independent labels, numerical execution and throughput only; no acquisition."})


def main() -> None:
    directory = Path(sys.argv[1])
    protocol, request = read_json(directory / "protocol.json"), read_json(directory / "request.json")
    engine, work = backend(protocol), Work()
    try:
        if request["kind"] == "preflight":
            preflight(engine, protocol, directory, work)
        elif request["kind"] == "replay":
            replay(engine, protocol, request, directory, work)
        else:
            train(engine, protocol, request, directory, work)
    finally:
        write(directory, "work.json", work.record())
        write(directory, "worker-resources.json", {"peak_rss_bytes": peak_rss_bytes(), "backend": engine.torch.__version__,
                                                   "threads": 1, "dtype": "float32", "device": "cpu", "python": sys.version,
                                                   "platform": platform.platform(), "deterministic_algorithms": True})


if __name__ == "__main__":
    main()
