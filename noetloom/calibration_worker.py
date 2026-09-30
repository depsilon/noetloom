"""Optional numerical worker for EXP-0005; launched by its serialized driver."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import platform
import random
import sys
import time

from .calibration_contracts import acquisition_gate
from .calibration_data import generate, score
from .calibration_model import forward_ops, parameter_count, scalar_forward
from .calibration_records import publish_fit, write
from .contracts import ContractError, canonical_bytes, read_json
from .learning_worker import peak_rss_bytes
from .storage import file_digest


def backend(protocol: dict):
    from . import calibration_torch as engine
    torch = engine.torch
    if torch.__version__.split("+")[0] != protocol["training"]["version"]:
        raise ContractError("calibration numerical backend version differs")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    return engine


def tensors(engine, rows: list[dict]):
    # Only values cross the learned forward boundary; labels are loss/scorer targets.
    return (engine.torch.tensor([row["values"] for row in rows], dtype=engine.torch.float32),
            engine.torch.tensor([row["expected"] for row in rows], dtype=engine.torch.long))


def evaluate(engine, model, rows: list[dict]) -> dict:
    if not rows:
        return {"cross_entropy": None, "scored": {}, "predictions": [], "logits": []}
    x, y = tensors(engine, rows)
    with engine.torch.no_grad():
        logits = model(x)
        loss = engine.F.cross_entropy(logits, y).item()
        predictions = logits.argmax(1).tolist()
    if not math.isfinite(loss):
        raise ContractError("nonfinite calibration evaluation")
    return {"cross_entropy": loss, "scored": score(rows, predictions),
            "predictions": predictions, "logits": logits.tolist()}


def metric_record(value: dict) -> dict:
    return {key: value[key] for key in ("cross_entropy", "scored")}


def select_measurement(measurements: list[dict], request: dict) -> int:
    rule = request.get("checkpoint_selection", "minimum_validation_loss")
    if rule == "last":
        if request["kind"] != "confirmation":
            raise ContractError("last-step selection belongs only to the explicit confirmation amendment")
        return len(measurements) - 1
    if rule != "minimum_validation_loss":
        raise ContractError("unregistered calibration checkpoint selection")
    objective = "training" if request["stage"] == "tiny" else "validation"
    return min(range(len(measurements)), key=lambda i: (measurements[i][objective]["cross_entropy"], measurements[i]["step"]))


def require_confirmation_payloads(directory: Path, request: dict, selected: dict, protocol: dict) -> None:
    if request["kind"] == "confirmation":
        expected = acquisition_gate(request["stage"], selected, protocol)["passed"]
        if any((directory / name).is_file() != expected for name in ("evaluation-data.json", "untrained.json")):
            raise ContractError("confirmation evaluation and initialization-control payloads do not match acquisition admission")


def reference_check(engine, model, cases: list[dict]) -> dict:
    # Full replay uses a fresh numerical process; these checks independently implement
    # every operation and sample up to 24 observed fields spanning the available rows.
    count = min(24, len(cases))
    indices = sorted({round(i * (len(cases) - 1) / max(1, count - 1)) for i in range(count)})
    rows = [cases[i] for i in indices]
    values, _ = tensors(engine, rows)
    with engine.torch.no_grad():
        intermediate = model.construct(values).tolist()
        logits = model(values).tolist()
    snapshot = model.snapshot(0)
    maximum = 0.0
    for row, actual, latent in zip(rows, logits, intermediate):
        expected, encoded = scalar_forward(snapshot, row["values"])
        maximum = max(maximum, *(abs(a - b) for a, b in zip(actual + latent, expected + encoded)))
        if actual.index(max(actual)) != expected.index(max(expected)):
            raise ContractError("scalar/tensor calibration classes differ")
    if maximum > 2e-4:
        raise ContractError("scalar/tensor calibration parity failed")
    return {"cases": len(rows), "maximum_absolute_error": maximum, "tolerance": 2e-4}


def diagnostics(engine, model, training: list[dict], validation: list[dict]) -> dict:
    train_x, _ = tensors(engine, training)
    valid_x, _ = tensors(engine, validation)
    with engine.torch.no_grad():
        training_state = model.construct(train_x)
        state = model.construct(valid_x)
        variation = state[:, :16].var(0, unbiased=False).mean().item()
        altered = state.clone()
        altered[:, :16] = training_state[:, :16].mean(0)
        predictions = model.network("solver", altered).argmax(1).tolist()
    return {"mean_intermediate_variance": variation,
            "constant_constructed_state": score(validation, predictions),
            "scope": "Replace constructed sixteen values by training mean; bypass raw values remain available."}


def verify_selected(engine, model, data: dict, fit: dict, protocol: dict, request: dict, directory: Path) -> dict:
    results = {name: evaluate(engine, model, rows) for name, rows in data.items()}
    selected = fit["measurements"][fit["selected_measurement"]]
    for group in ("training", "validation"):
        if metric_record(results[group]) != selected[group]:
            raise ContractError("restored snapshot does not reproduce fitting selection metrics")
    passed = acquisition_gate(request["stage"], selected, protocol)["passed"]
    evaluation = []
    # Development transformation access is a separate replay action admitted only
    # after all registered seeds pass. Fitting cannot grant that arm-level permission.
    if request["kind"] == "confirmation" and request["stage"] == "mixed" and passed:
        evaluation = generate(protocol, "mixed", confirmation=request["kind"] == "confirmation")["evaluation"]
        write(directory, "evaluation-data.json", {"rows": evaluation})
        results["evaluation"] = evaluate(engine, model, evaluation)
        untrained = engine.Model.restore(read_json(directory / "parameters-0.json"))
        write(directory, "untrained.json", evaluate(engine, untrained, evaluation))
    write(directory, "predictions.json", results)
    reference = reference_check(engine, model, data["training"] + data["validation"])
    diagnostic = diagnostics(engine, model, data["training"], data["validation"]) if data["validation"] else None
    presentations = 2 * len(data["training"]) + 3 * len(data["validation"]) + len(evaluation) + 3 * reference["cases"]
    if not data["validation"]:
        presentations -= len(data["training"])
    if evaluation:
        presentations += len(evaluation)  # Registered untrained-initialization control.
    return {"reference": reference, "acquisition": fit["acquisition"], "diagnostics": diagnostic,
            "verification_presentations": presentations,
            "evaluation_cases": len(evaluation), "evaluation_scored": results["evaluation"]["scored"]}


def train(engine, protocol: dict, request: dict, directory: Path) -> None:
    model = engine.Model(request["arm"], request["seed"])
    condition = next(c for c in protocol["conditions"] if c["name"] == request["condition"])
    steps = 8 if request["kind"] == "injection" else condition["steps"]
    data = generate(protocol, request["stage"], include_evaluation=False)
    write(directory, "data.json", data)
    x, y = tensors(engine, data["training"])
    opt = engine.torch.optim.Adam(model.parameters(), lr=condition["learning_rate"], betas=(0.9, 0.999),
                                 eps=1e-8, weight_decay=0.0, foreach=False, fused=False)
    rng = random.Random(request["seed"] ^ 44119)
    measure_at = {round(steps * fraction) for fraction in protocol["training"]["measurement_fractions"]}
    measurements, losses = [], []
    started = time.monotonic()
    write(directory, "fitting-status.json", {"status": "running", "completed_updates": 0})
    for step in range(steps + 1):
        if step:
            indices = [rng.randrange(len(x)) for _ in range(protocol["training"]["batch_size"])]
            opt.zero_grad(set_to_none=True)
            loss = engine.F.cross_entropy(model(x[indices]), y[indices])
            if not engine.torch.isfinite(loss):
                raise ContractError("nonfinite calibration training loss")
            loss.backward()
            engine.torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
            opt.step()
            losses.append(loss.item())
        if step in measure_at:
            name = f"parameters-{step}.json"
            write(directory, name, model.snapshot(step))
            measurement = {"step": step, "elapsed_seconds": time.monotonic() - started,
                           "training": metric_record(evaluate(engine, model, data["training"])),
                           "validation": metric_record(evaluate(engine, model, data["validation"])),
                           "snapshot": name, "snapshot_sha256": file_digest(directory / name)}
            measurements.append(measurement)
            write(directory, "fit-progress.json", {"completed_updates": step, "losses": losses,
                                                    "measurements": measurements})
    selected_index = select_measurement(measurements, request)
    selected = measurements[selected_index]
    snapshot = read_json(directory / selected["snapshot"])
    write(directory, "selected.json", snapshot)
    fitting_presentations = steps * 16 + len(measurements) * (len(data["training"]) + len(data["validation"]))
    fit = {"schema_version": "noetloom.calibration_fit.v1", "identity": request,
           "data_sha256": file_digest(directory / "data.json"), "protocol_sha256": file_digest(directory / "protocol.json"),
           "completed_updates": steps, "fitting_presentations": fitting_presentations,
           "fitting_seconds": time.monotonic() - started, "worker_peak_rss_bytes": peak_rss_bytes(),
           "parameter_count": parameter_count(request["arm"]), "forward_scalar_ops": forward_ops(request["arm"]),
           "training_proxy_ops": steps * (3 * 16 * forward_ops(request["arm"]) + 10 * parameter_count(request["arm"])),
           "losses": losses, "measurements": measurements, "selected_measurement": selected_index,
           "selected_sha256": file_digest(directory / "selected.json"), "acquisition": acquisition_gate(request["stage"], selected, protocol)}
    publish_fit(directory, fit, lambda: verify_selected(engine, engine.Model.restore(snapshot), data, fit, protocol, request, directory),
                inject_failure=request["kind"] == "injection")


def replay(engine, protocol: dict, request: dict, directory: Path) -> None:
    original = Path(request["original"])
    fit, data = read_json(original / "fit.json"), read_json(original / "data.json", 8 * 1024**2)
    old_request = read_json(original / "request.json")
    if data != generate(protocol, old_request["stage"], include_evaluation=False):
        raise ContractError("replay data differs from development generation")
    measurements = fit["measurements"]
    steps = next(c["steps"] for c in protocol["conditions"] if c["name"] == old_request["condition"])
    expected_steps = [round(steps * fraction) for fraction in protocol["training"]["measurement_fractions"]]
    if (fit["identity"] != old_request or fit["completed_updates"] != steps or len(fit["losses"]) != steps
            or [row["step"] for row in measurements] != expected_steps
            or fit["data_sha256"] != file_digest(original / "data.json")
            or fit["protocol_sha256"] != file_digest(original / "protocol.json")
            or fit["selected_sha256"] != file_digest(original / "selected.json")):
        raise ContractError("fitting identity, update count, snapshots or measurement schedule differs")
    for measurement in measurements:
        path = original / measurement["snapshot"]
        if file_digest(path) != measurement["snapshot_sha256"]:
            raise ContractError("fitting snapshot identity differs")
        snapshot = read_json(path)
        if (snapshot["arm"], snapshot["seed"], snapshot["step"]) != (old_request["arm"], old_request["seed"], measurement["step"]):
            raise ContractError("fitting snapshot arm, seed or step differs")
        model = engine.Model.restore(snapshot)
        for group in ("training", "validation"):
            if metric_record(evaluate(engine, model, data[group])) != measurement[group]:
                raise ContractError("replayed fitting curve differs from saved metrics")
    chosen = select_measurement(measurements, old_request)
    if fit["selected_measurement"] != chosen or read_json(original / "selected.json") != read_json(original / measurements[chosen]["snapshot"]):
        raise ContractError("selected snapshot differs from registered checkpoint rule")
    require_confirmation_payloads(original, old_request, measurements[chosen], protocol)
    model = engine.Model.restore(read_json(original / "selected.json"))
    if (original / "evaluation-data.json").is_file():
        evaluation = read_json(original / "evaluation-data.json")["rows"]
        if evaluation != generate(protocol, "mixed", confirmation=old_request["kind"] == "confirmation")["evaluation"]:
            raise ContractError("evaluation data differs from the frozen partition")
        data["evaluation"] = evaluation
    fresh = {name: evaluate(engine, model, rows) for name, rows in data.items()}
    if fresh != read_json(original / "predictions.json", 8 * 1024**2):
        raise ContractError("fresh calibration predictions or independently scored results differ")
    reference = reference_check(engine, model, data["training"] + data["validation"])
    diagnostic = diagnostics(engine, model, data["training"], data["validation"]) if data["validation"] else None
    original_verification = read_json(original / "verification-status.json")
    if diagnostic != original_verification["diagnostics"] or acquisition_gate(old_request["stage"], measurements[chosen], protocol) != fit["acquisition"]:
        raise ContractError("replayed acquisition or diagnostic differs")
    count = len(measurements) * (len(data["training"]) + len(data["validation"])) + sum(len(v) for v in data.values()) + 3 * reference["cases"]
    if diagnostic:
        count += len(data["training"]) + 2 * len(data["validation"])
    if (original / "untrained.json").is_file():
        untrained = engine.Model.restore(read_json(original / "parameters-0.json"))
        if evaluate(engine, untrained, data["evaluation"]) != read_json(original / "untrained.json"):
            raise ContractError("replayed untrained-initialization control differs")
        count += len(data["evaluation"])
    if request.get("development_transfer"):
        transfer = generate(protocol, "mixed")["evaluation"]
        write(directory, "transfer-data.json", {"rows": transfer})
        write(directory, "transfer.json", evaluate(engine, model, transfer))
        transfer_reference = reference_check(engine, model, transfer)
        count += len(transfer) + 3 * transfer_reference["cases"]
        write(directory, "transfer-reference.json", transfer_reference)
    write(directory, "replay.json", {"status": "passed", "original_fit_sha256": file_digest(original / "fit.json"),
                                    "measurements": len(measurements), "predictions": sum(len(v) for v in data.values()),
                                    "case_presentations": count,
                                    "development_transfer": bool(request.get("development_transfer")),
                                    "reference": reference, "scope": "Inference and fitted curves replayed; optimization not rerun."})


def preflight(engine, protocol: dict, directory: Path) -> None:
    torch = engine.torch
    generator = torch.Generator().manual_seed(4811)
    x = torch.randn(16, 64, generator=generator).tanh()
    y = torch.arange(16) % 2
    report = {}
    for arm in protocol["arms"]:
        model = engine.Model(arm, 4717)
        opt = torch.optim.Adam(model.parameters(), lr=0.003, foreach=False, fused=False)
        timings = []
        for step in range(24):
            start = time.monotonic()
            opt.zero_grad(set_to_none=True)
            loss = engine.F.cross_entropy(model(x), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
            opt.step()
            if step >= 8:
                timings.append(time.monotonic() - start)
        projected = sum(timings) / len(timings) * 2048
        if projected > 70:
            raise ContractError("registered long condition is not feasible within preflight margin")
        # The field grammar is irrelevant for a numerical execution check.
        samples = [{"values": row, "expected": int(label)} for row, label in zip(x.tolist(), y.tolist())]
        reference = reference_check(engine, model, samples)
        report[arm] = {"parameter_count": parameter_count(arm), "forward_scalar_ops": forward_ops(arm),
                       "projected_long_fitting_seconds": projected, "reference": reference,
                       "timed_updates": len(timings), "warmup_updates": 8}
    write(directory, "preflight.json", {"arms": report, "scope": "Execution and throughput only; no acquisition claim."})


def main() -> None:
    directory = Path(sys.argv[1])
    protocol, request = read_json(directory / "protocol.json"), read_json(directory / "request.json")
    engine = backend(protocol)
    try:
        if request["kind"] == "preflight":
            preflight(engine, protocol, directory)
        elif request["kind"] == "replay":
            replay(engine, protocol, request, directory)
        else:
            train(engine, protocol, request, directory)
    finally:
        write(directory, "worker-resources.json", {"peak_rss_bytes": peak_rss_bytes(), "backend": engine.torch.__version__,
                                                   "threads": engine.torch.get_num_threads(), "dtype": "float32", "device": "cpu",
                                                   "python": sys.version, "platform": platform.platform(),
                                                   "deterministic_algorithms": engine.torch.are_deterministic_algorithms_enabled()})


if __name__ == "__main__":
    main()
