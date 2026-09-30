"""One bounded training/preflight worker, launched under the parent run lease."""
from __future__ import annotations

import json
import math
from pathlib import Path
import resource
import subprocess
import sys
import time
from typing import Any

from .contracts import ContractError, canonical_bytes, read_json
from .learning_data import generate, observations_only, query_prefixes, reference_answers
from .storage import file_digest, tree_bytes


def write(directory: Path, name: str, value: Any) -> None:
    if Path(name).name != name:
        raise ContractError("artifact must be one filename")
    payload = canonical_bytes(value)
    if len(payload) + tree_bytes(directory) > 15 * 1024**2:
        raise ContractError("learning payloads exceed the 15 MiB pre-completion allowance")
    with (directory / name).open("xb") as handle:
        handle.write(payload)


def native(binary: Path, directory: Path, parameters: str, observations: str,
           output: str, mode: str = "evaluate", extras: list[str] | None = None) -> dict:
    command = [str(binary), mode, str(directory / parameters), str(directory / observations),
               str(directory / output), *(extras or [])]
    started = time.monotonic()
    result = subprocess.run(command, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ContractError(f"native learning evaluation failed: {result.stderr[:2000].decode(errors='replace')}")
    receipt = read_json(directory / output, 8 * 1024**2)
    receipt["driver_process_seconds"] = time.monotonic() - started
    return receipt


def peak_rss_bytes(who: int = resource.RUSAGE_SELF) -> int:
    value = resource.getrusage(who).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def check_native_identity(receipt: dict, parameters: Path, observations: Path, source: dict) -> None:
    if receipt["parameter_sha256"] != file_digest(parameters) or receipt["input_sha256"] != file_digest(observations):
        raise ContractError("native receipt input/parameter identity differs")
    if any(receipt.get("build", {}).get(key) != value for key, value in source.items()):
        raise ContractError("native receipt Rust source differs")


def parity(receipt: dict, rows: list[dict], tensor_result: dict) -> float:
    native_rows = receipt["results"]
    if [row["id"] for row in native_rows] != [row["id"] for row in rows]:
        raise ContractError("native episode identity/order differs")
    predictions = [prediction for row in native_rows for prediction in row["predictions"]]
    expected_ids = [i for _ in rows for i in range(8)]
    if [prediction["query_id"] for prediction in predictions] != expected_ids:
        raise ContractError("native query identity/order differs")
    if len(predictions) != len(tensor_result["logits"]):
        raise ContractError("native/tensor query counts differ")
    maximum = 0.0
    for native_row, tensor_logits, tensor_prediction in zip(predictions, tensor_result["logits"], tensor_result["predictions"]):
        if len(native_row["logits"]) != 5:
            raise ContractError("native logits have wrong shape")
        for actual, expected in zip(native_row["logits"], tensor_logits):
            error = abs(actual - expected)
            maximum = max(maximum, error)
            if not math.isfinite(actual) or error > 3e-5 + 3e-5 * abs(expected):
                raise ContractError("native logits differ from independently reloaded tensor parameters")
        if native_row["prediction"] != tensor_prediction:
            raise ContractError("native and tensor predictions differ")
    return maximum


def score(receipt: dict, rows: list[dict]) -> dict:
    if [row["id"] for row in receipt["results"]] != [row["id"] for row in rows]:
        raise ContractError("scorer episode identity/order mismatch")
    totals: dict[str, list[int]] = {}
    phases: dict[str, list[int]] = {}
    metrics: dict[str, int | float] = {}
    for result, row in zip(receipt["results"], rows):
        if reference_answers(row["observations"]) != [answer["expected"] for answer in row["answers"]]:
            raise ContractError("generator differs from independent exact reference")
        predictions = result["predictions"]
        if len(predictions) != 8:
            raise ContractError("scorer requires exactly eight predictions")
        family = row["id"].rsplit("-", 1)[0]
        for prediction, answer in zip(predictions, row["answers"]):
            if prediction["query_id"] != answer["query_id"] or type(prediction["prediction"]) is not int or not 0 <= prediction["prediction"] <= 4:
                raise ContractError("invalid prediction identity or class")
            correct = int(prediction["prediction"] == answer["expected"])
            for groups, group in ((totals, family), (phases, family + ":" + answer["phase"])):
                counts = groups.setdefault(group, [0, 0])
                counts[0] += correct
                counts[1] += 1
        for name, value in result["metrics"].items():
            if type(value) is not int or value < 0:
                raise ContractError("invalid native integer metric")
            metrics[name] = max(metrics.get(name, 0), value) if name.startswith("peak_") else metrics.get(name, 0) + value
    def rates(groups: dict[str, list[int]]) -> dict:
        return {name: {"correct": pair[0], "queries": pair[1], "accuracy": pair[0] / pair[1]}
                for name, pair in sorted(groups.items())}
    correct = sum(pair[0] for pair in totals.values())
    count = sum(pair[1] for pair in totals.values())
    return {"families": rates(totals), "phases": rates(phases), "accuracy": correct / count,
            "correct": correct, "queries": count, "native_metrics": metrics}


def preflight(directory: Path, protocol: dict, binary: Path, rust_source: dict) -> None:
    started = time.monotonic()
    from . import learning_torch as backend
    environment = backend.configure()
    development = generate(protocol, development=True)["datasets"]["development"]
    views = backend.tensor_views(query_prefixes(development))
    gradients = backend.check_gradients(views)
    timings = {}
    parity_errors = {}
    write(directory, "development-observations.json", observations_only(development))
    for arm in protocol["arms"]:
        model = backend.CellModel(812, arm)
        opt = backend.optimizer(model)
        indices = backend.sample_indices(812, 24, len(views["targets"]))
        for item in indices[:8]:
            backend.update(model, opt, backend.batch(views, item))
        timer = time.monotonic()
        for item in indices[8:]:
            backend.update(model, opt, backend.batch(views, item))
        timings[arm] = (time.monotonic() - timer) / 16
        filename = f"development-{arm}.json"
        write(directory, filename, model.artifact(24))
        receipt = native(binary, directory, filename, "development-observations.json", f"native-{arm}.json")
        check_native_identity(receipt, directory / filename, directory / "development-observations.json", rust_source)
        parity_errors[arm] = parity(receipt, development, backend.evaluate(model, views))
    selected = next((steps for steps in protocol["training"]["candidate_steps"]
                     if max(timings.values()) * steps < protocol["preflight"]["extrapolated_training_seconds"]), None)
    if selected is None:
        raise ContractError("backend-budget rejection: neither registered training count fits")
    # Freeze all observations/labels only after the unscored development timing decision.
    write(directory, "data.json", generate(protocol))
    write(directory, "preflight.json", {"status": "passed", "environment": environment,
          "gradients": gradients, "seconds_per_step": timings, "selected_steps": selected,
          "parity_maximum_logit_error": parity_errors, "training_quality_used_for_selection": False,
          "peak_rss_bytes": peak_rss_bytes(), "elapsed_seconds": time.monotonic() - started})


def train(directory: Path, protocol: dict, binary: Path, rust_source: dict,
          admission: Path, arm: str, seed: int) -> None:
    started = time.monotonic()
    from . import learning_torch as backend
    environment = backend.configure()
    data = read_json(admission / "data.json", 8 * 1024**2)["datasets"]
    selected_steps = read_json(admission / "preflight.json")["selected_steps"]
    if selected_steps not in protocol["training"]["candidate_steps"]:
        raise ContractError("unregistered preflight training count")
    prep_start = time.monotonic()
    train_views = backend.tensor_views(query_prefixes(data["train"]))
    validation_views = backend.tensor_views(query_prefixes(data["validation"]))
    prep_seconds = time.monotonic() - prep_start
    model = backend.CellModel(seed, arm)
    write(directory, "initial.json", model.artifact(0))
    opt = backend.optimizer(model)
    indices = backend.sample_indices(seed, selected_steps, len(train_views["targets"]))
    checkpoints = {int(selected_steps * fraction) for fraction in protocol["training"]["validation_fractions"]}
    losses, validation = [], []
    best_loss = float("inf")
    best = None
    train_seconds = 0.0
    for step, item in enumerate(indices, 1):
        update_start = time.monotonic()
        loss = backend.update(model, opt, backend.batch(train_views, item))
        train_seconds += time.monotonic() - update_start
        losses.append(loss)
        if step in checkpoints:
            evaluated = backend.evaluate(model, validation_views)
            loss = evaluated["cross_entropy"]
            artifact = model.artifact(step)
            write(directory, f"checkpoint-{step}.json", artifact)
            validation.append({"step": step, "cross_entropy": loss})
            if loss < best_loss:
                best_loss, best = loss, artifact
    if best is None:
        raise ContractError("no registered checkpoint was evaluated")
    write(directory, "selected.json", best)
    # Reload the exported artifact, then independently check native inference.
    replica = backend.CellModel.from_artifact(read_json(directory / "selected.json"))
    test_rows = [row for family in protocol["data"]["test_families"] for row in data[f"test_{family}"]]
    write(directory, "observations.json", observations_only(test_rows))
    tensor_start = time.monotonic()
    tensor_result = backend.evaluate(replica, backend.tensor_views(query_prefixes(test_rows)))
    tensor_seconds = time.monotonic() - tensor_start
    write(directory, "tensor-parity.json", tensor_result)
    receipt = native(binary, directory, "selected.json", "observations.json", "native.json")
    check_native_identity(receipt, directory / "selected.json", directory / "observations.json", rust_source)
    maximum = parity(receipt, test_rows, tensor_result)
    scored = score(receipt, test_rows)
    write(directory, "restart-observations.json", observations_only(test_rows[:1]))
    split = len(test_rows[0]["observations"]) // 2
    extras = [str(directory / "persistent"), str(split)]
    prefix = native(binary, directory, "selected.json", "restart-observations.json", "persistent-prefix.json", "persist", extras)
    suffix = native(binary, directory, "selected.json", "restart-observations.json", "persistent-suffix.json", "resume", extras)
    for segment in (prefix, suffix):
        check_native_identity(segment, directory / "selected.json", directory / "restart-observations.json", rust_source)
    restarted = {"results": [{"id": test_rows[0]["id"], "predictions":
                 prefix["results"][0]["predictions"] + suffix["results"][0]["predictions"]}]}
    parity(restarted, test_rows[:1], {"logits": tensor_result["logits"][:8], "predictions": tensor_result["predictions"][:8]})
    presentations = selected_steps * 16 + len(validation) * 64 * 8 + 2 * len(test_rows) * 8 + 8
    if presentations > protocol["budget"]["max_query_presentations_per_run"]:
        raise ContractError("actual query presentations exceed admission")
    write(directory, "report.json", {"status": "completed", "arm": arm, "seed": seed,
          "scored": scored, "environment": environment, "steps": selected_steps,
          "selected_step": best["step"], "validation": validation, "training_losses": losses,
          "parameter_count": sum(p.numel() for p in model.parameters()),
          "trainable_parameter_count": sum(p.numel() for p in model.parameters() if p.requires_grad),
          "optimizer_state_scalar_count": sum(value.numel() for state in opt.state.values() for value in state.values() if hasattr(value, "numel")),
          "query_presentations": presentations, "training_padded_event_encodings": selected_steps * 16 * 32 if arm != "no_history" else 0,
          "cost_scope": "Training computes padded dense prefixes and autograd; inference separately counts native descriptors, payload operations and nominal arithmetic. No total FLOP estimate or OS sandbox claim.",
          "data_preparation_seconds": prep_seconds, "optimizer_step_seconds": train_seconds,
          "tensor_verification_seconds": tensor_seconds, "native_evaluation_seconds": receipt["elapsed_seconds"],
          "native_process_seconds": receipt["driver_process_seconds"],
          "initialization_payload_bytes_per_episode": 32,
          "elapsed_seconds": time.monotonic() - started, "peak_rss_bytes": peak_rss_bytes(),
          "native_children_peak_rss_bytes": peak_rss_bytes(resource.RUSAGE_CHILDREN),
          "maximum_logit_error": maximum, "persistent_restart": "passed"})


def main() -> None:
    directory = Path(sys.argv[2])
    request = read_json(directory / "request.json")
    protocol = read_json(directory / "protocol.json")
    if sys.argv[1] == "preflight":
        preflight(directory, protocol, Path(request["binary"]), request["rust_source"])
    elif sys.argv[1] == "train":
        train(directory, protocol, Path(request["binary"]), request["rust_source"],
              Path(request["admission"]), request["arm"], request["seed"])
    else:
        raise ContractError("unknown learning worker operation")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
        raise
