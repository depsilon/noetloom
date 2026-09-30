"""EXP-0003 worker, always launched under the experiment driver's resource lease."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import time

from .allocation_data import generate
from .contracts import ContractError, read_json
from .learning_data import observations_only, query_prefixes
from .learning_worker import check_native_identity, native, parity, peak_rss_bytes, score, write


def allocation_parity(receipt: dict, rows: list[dict], tensor: dict) -> float:
    maximum = parity(receipt, rows, tensor)
    native_rows = [prediction for row in receipt["results"] for prediction in row["predictions"]]
    for index, prediction in enumerate(native_rows):
        if prediction.get("continued") is not tensor["continued"][index]:
            raise ContractError("native/tensor allocation decisions differ")
        if len(prediction.get("gate_features", [])) != 6:
            raise ContractError("native gate features are missing")
        for actual, expected in zip(prediction["gate_features"], tensor["gate_features"][index]):
            if not math.isfinite(actual) or abs(actual - expected) > 3e-5:
                raise ContractError("native/tensor gate features differ")
        actual_score = prediction.get("gate_score")
        if not isinstance(actual_score, (float, int)) or not math.isfinite(actual_score) or abs(actual_score - tensor["gate_scores"][index]) > 3e-5:
            raise ContractError("native/tensor gate score differs")
    if sum(prediction["continued"] for prediction in native_rows) != sum(row["metrics"]["continued_queries"] for row in receipt["results"]):
        raise ContractError("continuation counters differ from query evidence")
    if sum(tensor["payload_reads"]) != sum(row["metrics"]["payload_reads"] for row in receipt["results"]):
        raise ContractError("native payload reads differ from admitted allocation")
    return maximum


def _backend():
    from . import allocation_torch as backend
    from . import learning_torch as reader
    environment = reader.configure()
    return backend, reader, environment


def _parent(request: dict, seed: int) -> tuple[dict, dict]:
    record = next(row for row in request["parents"] if row["seed"] == seed)
    return record, read_json(Path(record["checkpoint_path"]))


def _endpoint_tensor(prepared: dict, arm: str) -> dict:
    logits = prepared[arm]
    return {"logits": logits.tolist(), "predictions": logits.argmax(1).tolist()}


def preflight(directory: Path, protocol: dict, request: dict) -> None:
    started = time.monotonic()
    backend, reader, environment = _backend()
    _, parent_artifact = _parent(request, protocol["seeds"][0])
    parent = reader.CellModel.from_artifact(parent_artifact)
    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    rows = generate(protocol, development=True)["datasets"]["development"]
    views = reader.tensor_views(query_prefixes(rows))
    prepared = backend.prepare(parent, views)
    observed_branches = {name: prepared[name] for name in ("features", "top_one", "dense", "count")}
    gradients = backend.check_gradients(prepared)
    gate = backend.Gate(812)
    try:
        backend.infer(gate, {**observed_branches, "targets": views["targets"]})
    except ContractError:
        pass
    else:
        raise ContractError("allocation inference accepted a label-bearing input")
    opt = backend.optimizer(gate)
    batches = backend.sample_indices(812, 24, len(prepared["count"]))
    for batch in batches[:8]:
        backend.update(gate, opt, prepared, batch)
    timer = time.monotonic()
    for batch in batches[8:]:
        backend.update(gate, opt, prepared, batch)
    seconds_per_step = (time.monotonic() - timer) / 16
    steps = next((count for count in protocol["training"]["candidate_steps"]
                  if seconds_per_step * count < protocol["preflight"]["extrapolated_training_seconds"]), None)
    if steps is None:
        raise ContractError("allocation throughput admission rejected both registered counts")
    write(directory, "development-observations.json", observations_only(rows))
    errors = {}
    binary = Path(request["binary"])
    cases = [("top_one", None), ("dense", None), ("adaptive", gate.artifact()),
             ("halt", {"weights": [0.0] * 6, "bias": -10.0}),
             ("continue", {"weights": [0.0] * 6, "bias": 10.0})]
    for name, gate_artifact in cases:
        arm = name if name in {"top_one", "dense"} else "adaptive"
        params = backend.parameters(parent_artifact, arm, gate_artifact)
        write(directory, f"development-{name}.json", params)
        receipt = native(binary, directory, f"development-{name}.json", "development-observations.json", f"native-{name}.json")
        check_native_identity(receipt, directory / f"development-{name}.json", directory / "development-observations.json", request["rust_source"])
        if arm == "adaptive":
            tensor = backend.infer(backend.Gate.from_artifact(gate_artifact), observed_branches)
            errors[name] = allocation_parity(receipt, rows, tensor)
        else:
            errors[name] = parity(receipt, rows, _endpoint_tensor(prepared, arm))
    # Freeze final examples only after development timing selected a count.
    write(directory, "data.json", generate(protocol))
    write(directory, "preflight.json", {"status": "passed", "environment": environment,
          "selected_steps": steps, "seconds_per_step": seconds_per_step, "gradients": gradients,
          "inference_refuses_label_fields": True,
          "parity_maximum_logit_errors": errors, "peak_rss_bytes": peak_rss_bytes(),
          "elapsed_seconds": time.monotonic() - started, "test_quality_used": False})


def train(directory: Path, protocol: dict, request: dict) -> None:
    started = time.monotonic()
    backend, reader, environment = _backend()
    seed = request["seed"]
    parent_record, parent_artifact = _parent(request, seed)
    parent = reader.CellModel.from_artifact(parent_artifact)
    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    admission = Path(request["admission"])
    data = read_json(admission / "data.json", 8 * 1024**2)["datasets"]
    steps = read_json(admission / "preflight.json")["selected_steps"]
    timer = time.monotonic()
    train_views = reader.tensor_views(query_prefixes(data["train"]))
    validation_views = reader.tensor_views(query_prefixes(data["validation"]))
    training = backend.prepare(parent, train_views)
    validation = backend.prepare(parent, validation_views)
    preparation_seconds = time.monotonic() - timer
    gate = backend.Gate(seed)
    write(directory, "parent.json", parent_artifact)
    write(directory, "initial-gate.json", gate.artifact())
    opt = backend.optimizer(gate)
    batches = backend.sample_indices(seed, steps, len(training["count"]))
    validation_steps = {int(steps * fraction) for fraction in protocol["training"]["validation_fractions"]}
    checkpoints, losses = [], []
    best_objective, selected_step, selected_gate = math.inf, None, None
    timer = time.monotonic()
    for step, batch in enumerate(batches, 1):
        losses.append(backend.update(gate, opt, training, batch))
        if step in validation_steps:
            value = backend.evaluate(gate, validation)["validation_objective"]
            artifact = gate.artifact()
            write(directory, f"gate-step-{step}.json", artifact)
            checkpoints.append({"step": step, "objective": value})
            if value < best_objective:
                best_objective, selected_step, selected_gate = value, step, artifact
    fitting_seconds = time.monotonic() - timer
    if selected_gate is None:
        raise ContractError("no validated allocation checkpoint")
    write(directory, "selected-gate.json", selected_gate)
    # Reload exported weights before final inference. No final score may select weights.
    selected = backend.Gate.from_artifact(read_json(directory / "selected-gate.json"))
    rows = [row for family in protocol["data"]["test_families"] for row in data[f"test_{family}"]]
    final_views = reader.tensor_views(query_prefixes(rows))
    final = backend.branches(parent, reader.features(final_views))
    write(directory, "observations.json", observations_only(rows))
    reports = {}
    binary = Path(request["binary"])
    for arm in protocol["arms"]:
        params = backend.parameters(parent_artifact, arm, selected_gate)
        write(directory, f"parameters-{arm}.json", params)
        tensor = backend.infer(selected, final) if arm == "adaptive" else _endpoint_tensor(final, arm)
        write(directory, f"tensor-{arm}.json", tensor)
        receipt = native(binary, directory, f"parameters-{arm}.json", "observations.json", f"native-{arm}.json")
        check_native_identity(receipt, directory / f"parameters-{arm}.json", directory / "observations.json", request["rust_source"])
        error = allocation_parity(receipt, rows, tensor) if arm == "adaptive" else parity(receipt, rows, tensor)
        reports[arm] = {"scored": score(receipt, rows), "maximum_logit_error": error,
                        "family_payload_bytes": {f"test_{family}": sum(result["metrics"]["payload_read_bytes"]
                            for result in receipt["results"] if result["id"].startswith(f"test_{family}-"))
                            for family in protocol["data"]["test_families"]},
                        "native_process_seconds": receipt["driver_process_seconds"],
                        "native_evaluation_seconds": receipt["elapsed_seconds"]}
    # Versioned persistent execution and a separate-process resume use the same selected gate.
    restart_row = next(row for row in rows if row["id"].startswith("test_interleaved-"))
    split = len(restart_row["observations"]) // 2
    write(directory, "restart-observations.json", observations_only([restart_row]))
    extras = [str(directory / "persistent-state"), str(split)]
    before = native(binary, directory, "parameters-adaptive.json", "restart-observations.json", "persistent-prefix.json", "persist", extras)
    after = native(binary, directory, "parameters-adaptive.json", "restart-observations.json", "persistent-resumed.json", "resume", extras)
    for receipt in (before, after):
        check_native_identity(receipt, directory / "parameters-adaptive.json", directory / "restart-observations.json", request["rust_source"])
    restarted = before["results"][0]["predictions"] + after["results"][0]["predictions"]
    original = read_json(directory / "native-adaptive.json", 8 * 1024**2)
    reference = next(row["predictions"] for row in original["results"] if row["id"] == restart_row["id"])
    if restarted != reference:
        raise ContractError("persistent allocation predictions differ across restart")
    # Reserve 16 presentations for restart; actual prefix+suffix executes eight queries.
    actual_queries = 2 * 512 + steps * 8 + 2 * 256 + 3 * 256 + 2 * 3 * 1024 + 8
    if actual_queries > protocol["budget"]["max_query_presentations_per_run"]:
        raise ContractError("allocation run exceeded query admission")
    write(directory, "report.json", {"status": "completed", "seed": seed, "parent": parent_record,
          "environment": environment, "inherited_trainable_scalars_now_frozen": 359,
          "gate_trainable_scalars": 7, "steps": steps, "selected_step": selected_step,
          "validation_checkpoints": checkpoints, "losses": losses, "query_presentations": actual_queries,
          "branch_preparation_seconds": preparation_seconds, "fitting_validation_seconds": fitting_seconds,
          "arms": reports, "restart_predictions": len(restarted), "restart_passed": True,
          "peak_rss_bytes": peak_rss_bytes(), "elapsed_seconds": time.monotonic() - started,
          "measurement_scope": "Counterfactual preparation reads all payloads. Native metrics measure each deployed policy; sampled/process high-water RSS is not a sandbox."})


def main() -> int:
    kind, directory = sys.argv[1], Path(sys.argv[2])
    protocol, request = read_json(directory / "protocol.json"), read_json(directory / "request.json")
    if kind == "preflight":
        preflight(directory, protocol, request)
    elif kind == "train":
        train(directory, protocol, request)
    else:
        raise ContractError("unknown allocation worker mode")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
        raise SystemExit(1)
