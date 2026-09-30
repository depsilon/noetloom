"""EXP-0004 worker launched only by its admitted, serialized experiment driver."""
from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys
import time

from .contracts import ContractError, canonical_bytes, read_json
from .learning_worker import check_native_identity, peak_rss_bytes
from .representation_common import forward_ops, parameter_count, training_proxy
from .representation_data import generate, observations, score, validate_observations
from .storage import tree_bytes


def write(directory: Path, name: str, value: object) -> None:
    if Path(name).name != name:
        raise ContractError("artifact must be one filename")
    protocol, request = read_json(directory / "protocol.json"), read_json(directory / "request.json")
    maximum = (protocol["preflight"]["max_output_bytes"] if request["kind"] == "preflight"
               else protocol["budget"]["max_output_bytes_per_run"])
    payload = canonical_bytes(value)
    if tree_bytes(directory) + len(payload) + 65536 > maximum:
        raise ContractError("representation artifact exceeds pre-completion admission")
    with (directory / name).open("xb") as handle:
        handle.write(payload)


def parity(receipt: dict, tensor: dict, tolerance: float = 2e-4) -> float:
    if receipt.get("schema_version") != "noetloom.native_representation.v1":
        raise ContractError("wrong native representation schema")
    rows = receipt.get("rows")
    if not isinstance(rows, list) or len(rows) != len(tensor["predictions"]):
        raise ContractError("native/tensor representation counts differ")
    maximum = 0.0
    for index, row in enumerate(rows):
        if type(row.get("prediction")) is not int or row["prediction"] != tensor["predictions"][index]:
            raise ContractError("native/tensor representation classes differ")
        for actual, expected in ((row.get("logits"), tensor["logits"][index]),
                                 (row.get("intermediate"), tensor["intermediates"][index])):
            if not isinstance(actual, list) or len(actual) != len(expected):
                raise ContractError("native/tensor representation shape differs")
            for left, right in zip(actual, expected):
                if type(left) not in (int, float) or not math.isfinite(left) or not math.isfinite(right):
                    raise ContractError("nonfinite representation evidence")
                maximum = max(maximum, abs(left - right))
                if abs(left - right) > tolerance:
                    raise ContractError("native/tensor representation numerical mismatch")
    for key in ("transport_entropy", "transport_variance"):
        actual, expected = receipt.get(key), tensor.get(key)
        if expected is None:
            if actual is not None:
                raise ContractError("unexpected native transport statistic")
        elif (type(actual) not in (int, float) or not math.isfinite(actual)
              or abs(actual - expected) > tolerance):
            raise ContractError("native/tensor transport statistics differ")
    return maximum


def predictions(receipt: dict) -> list[int]:
    return [row["prediction"] for row in receipt["rows"]]


def checked_native(binary: Path, directory: Path, parameter_file: str, input_file: str,
                   output_file: str, source: dict, mode: str = "evaluate",
                   extras: list[str] | None = None) -> dict:
    arguments = ["0"] if extras is None and mode == "evaluate" else (extras or [])
    rss_limit = read_json(directory / "protocol.json")["budget"]["max_peak_rss_bytes"]
    command = [str(binary), mode, str(directory / parameter_file), str(directory / input_file),
               str(directory / output_file), *arguments]
    started, sampled_peak, samples = time.monotonic(), 0, 0
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        # Keep this child in the worker's group so the outer training monitor includes it.
        # Standalone replay also samples each native child; very short runs may have no sample.
        while child.poll() is None:
            if time.monotonic() - started > 30:
                raise ContractError("native representation process exceeded 30 seconds")
            observed = subprocess.run(["ps", "-o", "rss=", "-p", str(child.pid)],
                                      capture_output=True, text=True, timeout=5, check=False)
            if observed.returncode == 0 and observed.stdout.strip().isdigit():
                samples += 1
                sampled_peak = max(sampled_peak, int(observed.stdout.strip()) * 1024)
                if sampled_peak > rss_limit:
                    raise ContractError("native representation process exceeded sampled RSS admission")
            time.sleep(0.01)
        _, stderr = child.communicate()
        if child.returncode:
            raise ContractError(f"native representation execution failed: {stderr[:2000].decode(errors='replace')}")
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    receipt = read_json(directory / output_file, 8 * 1024**2)
    receipt["driver_process_seconds"] = time.monotonic() - started
    receipt["driver_native_rss_samples"] = samples
    receipt["driver_native_sampled_peak_rss_bytes"] = sampled_peak if samples else None
    check_native_identity(receipt, directory / parameter_file, directory / input_file, source)
    if receipt.get("schema_version") != "noetloom.native_representation.v1":
        raise ContractError("unrecognized native representation receipt")
    return receipt


def _backend(protocol: dict):
    from . import representation_torch as backend
    torch = backend.torch
    if torch.__version__.split("+")[0] != protocol["training"]["version"]:
        raise ContractError("EXP-0004 requires registered PyTorch 2.14.0")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    return backend, {"torch": torch.__version__, "device": "cpu", "dtype": "float32", "threads": 1,
                     "deterministic_algorithms": torch.are_deterministic_algorithms_enabled()}


def tensor_values(backend, observed: dict):
    validate_observations(observed)
    return backend.torch.tensor([sample["values"] for sample in observed["samples"]], dtype=backend.torch.float32)


def metrics(receipt: dict, arm: str, shift: bool = False) -> dict:
    count = len(receipt["rows"])
    expected = count * (forward_ops(arm) + (2064 if shift else 0))
    if (type(receipt["nominal_scalar_ops"]) is not int or receipt["nominal_scalar_ops"] != expected
            or receipt["parameter_count"] != parameter_count(arm) or receipt["raw_input_bytes"] != count * 256):
        raise ContractError("native representation work/parameter counts differ from registration")
    width = 64 if arm.startswith("fixed_") else 16
    reads = sum(row["state"]["activation_reads"]["payload_bytes"] for row in receipt["rows"])
    if reads != count * width * 4:
        raise ContractError("native intermediate-state read accounting differs")
    return {"cases": count, "nominal_scalar_ops": expected, "raw_input_bytes": count * 256,
            "intermediate_state_read_bytes": reads, "intermediate_state_write_bytes": count * width * 4,
            "peak_intermediate_payload_bytes": width * 4,
            "transport_entropy": receipt["transport_entropy"], "transport_variance": receipt["transport_variance"],
            "native_process_seconds": receipt["driver_process_seconds"],
            "native_evaluation_seconds": receipt["elapsed_seconds"],
            "native_rss_samples": receipt["driver_native_rss_samples"],
            "native_sampled_peak_rss_bytes": receipt["driver_native_sampled_peak_rss_bytes"]}


def diagnostic_summary(cases: list[dict], inferred: list[int]) -> dict:
    scored = score(cases, inferred)["diagnostic"]
    groups = [inferred[index:index + 3] for index in range(0, len(inferred), 3)]
    if not groups or any(len(group) != 3 for group in groups):
        raise ContractError("incomplete cross-surface diagnostic groups")
    agreement = sum(len(set(group)) == 1 for group in groups) / len(groups)
    return {"accuracy": scored["accuracy"], "all_three_agreement": agreement, "problems": len(groups)}


def preflight(directory: Path, protocol: dict, request: dict) -> None:
    started = time.monotonic()
    backend, environment = _backend(protocol)
    # Generation freezes the scientific splits; only development fields enter this computation.
    data = generate(protocol)
    cases = data["development"]
    observed = observations(cases)
    values = tensor_values(backend, observed)
    targets = backend.torch.tensor([case["expected"] for case in cases])
    write(directory, "development-inputs.json", observed)
    gradients = backend.check_gradients()
    timings, errors, costs = {}, {}, {}
    binary = Path(request["binary"])
    for arm in protocol["arms"]:
        model = backend.Model(arm, 73)
        opt = backend.optimizer(model)
        batches = backend.sample_indices(73, 24, len(values))
        for batch in batches[:8]:
            backend.update(model, opt, values, targets, batch)
        timer = time.monotonic()
        for batch in batches[8:]:
            backend.update(model, opt, values, targets, batch)
        timings[arm] = (time.monotonic() - timer) / 16
        parameter_file = f"development-{arm}.json"
        write(directory, parameter_file, model.artifact(24))
        tensor = backend.infer(model, values)
        receipt = checked_native(binary, directory, parameter_file, "development-inputs.json",
                                 f"native-development-{arm}.json", request["rust_source"])
        errors[arm] = parity(receipt, tensor)
        metrics(receipt, arm)
        costs[arm] = {"parameters": parameter_count(arm), "forward_ops": forward_ops(arm)}
    steps = next((count for count in protocol["training"]["candidate_steps"]
                  if max(timings.values()) * count < protocol["preflight"]["extrapolated_training_seconds"]), None)
    if steps is None:
        raise ContractError("representation throughput rejects both registered update counts")
    for arm in protocol["arms"]:
        if (training_proxy(arm, steps) > protocol["budget"]["max_training_proxy_ops"]
                or forward_ops(arm) > protocol["budget"]["max_forward_scalar_ops"]):
            raise ContractError("representation nominal computation exceeds admission")
    if (parameter_count("fixed_large") <= parameter_count("conditional")
            or forward_ops("fixed_large") <= forward_ops("conditional")
            or training_proxy("fixed_large", steps) < training_proxy("conditional", steps)):
        raise ContractError("larger fixed control does not cover conditional capacity/work")
    labelled = {"schema_version": observed["schema_version"], "samples": [{**observed["samples"][0], "expected": 1}]}
    try:
        tensor_values(backend, labelled)
    except ContractError:
        pass
    else:
        raise ContractError("tensor input boundary accepted a label field")
    write(directory, "rejected-label-input.json", labelled)
    check = subprocess.run([str(binary), "evaluate", str(directory / "development-conditional.json"),
                            str(directory / "rejected-label-input.json"), str(directory / "must-not-exist.json"), "0"],
                           capture_output=True, timeout=10, check=False)
    if check.returncode == 0 or b"unknown field" not in check.stderr or (directory / "must-not-exist.json").exists():
        raise ContractError("native input boundary did not reject label fields before execution")
    write(directory, "boundary-check.json", {"tensor_refused": True, "native_exit": check.returncode,
                                            "native_error": check.stderr.decode(errors="replace")})
    write(directory, "data.json", data)
    write(directory, "preflight.json", {"status": "passed", "environment": environment, "selected_steps": steps,
          "seconds_per_step": timings, "costs": costs, "gradients": gradients,
          "maximum_native_tensor_errors": errors, "inference_refuses_label_fields": True,
          "peak_rss_bytes": peak_rss_bytes(), "elapsed_seconds": time.monotonic() - started,
          "test_quality_used": False, "scope": "development throughput and implementation checks only"})


def train(directory: Path, protocol: dict, request: dict) -> None:
    started = time.monotonic()
    backend, environment = _backend(protocol)
    arm, seed = request["arm"], request["seed"]
    admission = Path(request["admission"])
    data = read_json(admission / "data.json", 8 * 1024**2)
    steps = read_json(admission / "preflight.json")["selected_steps"]
    if training_proxy(arm, steps) > protocol["budget"]["max_training_proxy_ops"]:
        raise ContractError("fitting proxy exceeds admission")
    cases = data["training"]
    values = backend.torch.cat([tensor_values(backend, observations(cases[offset:offset + 512]))
                                for offset in range(0, len(cases), 512)])
    targets = backend.torch.tensor([case["expected"] for case in cases])
    validation = tensor_values(backend, observations(data["validation"]))
    validation_targets = backend.torch.tensor([case["expected"] for case in data["validation"]])
    model = backend.Model(arm, seed)
    write(directory, "initial.json", model.artifact(0))
    opt = backend.optimizer(model)
    batches = backend.sample_indices(seed, steps, len(cases))
    validation_steps = {int(steps * fraction) for fraction in protocol["training"]["validation_fractions"]}
    checkpoints, losses = [], []
    best_loss, selected = math.inf, None
    timer = time.monotonic()
    for step, batch in enumerate(batches, 1):
        losses.append(backend.update(model, opt, values, targets, batch))
        if step in validation_steps:
            with backend.torch.no_grad():
                loss = float(backend.F.cross_entropy(model(validation), validation_targets))
            if not math.isfinite(loss):
                raise ContractError("nonfinite validation objective")
            artifact = model.artifact(step)
            write(directory, f"checkpoint-{step}.json", artifact)
            checkpoints.append({"step": step, "cross_entropy": loss})
            if loss < best_loss:
                best_loss, selected = loss, artifact
    fitting_seconds = time.monotonic() - timer
    if selected is None:
        raise ContractError("no validated representation checkpoint")
    write(directory, "selected.json", selected)
    model = backend.Model.from_artifact(read_json(directory / "selected.json"))
    rows = data["test"]
    observed = observations(rows)
    write(directory, "inputs.json", observed)
    tensor_input = tensor_values(backend, observed)
    tensor = backend.infer(model, tensor_input)
    write(directory, "tensor.json", tensor)
    binary = Path(request["binary"])
    receipt = checked_native(binary, directory, "selected.json", "inputs.json", "native.json", request["rust_source"])
    error = parity(receipt, tensor)
    results = {"scored": score(rows, predictions(receipt)), "metrics": metrics(receipt, arm),
               "maximum_native_tensor_error": error}
    shifted_result = None
    if arm == "conditional":
        shifted = backend.infer(model, tensor_input, shift_group=96)
        write(directory, "tensor-shifted.json", shifted)
        shifted_native = checked_native(binary, directory, "selected.json", "inputs.json", "native-shifted.json",
                                       request["rust_source"], extras=["96"])
        shifted_result = {"scored": score(rows, predictions(shifted_native)),
                          "metrics": metrics(shifted_native, arm, True),
                          "maximum_native_tensor_error": parity(shifted_native, shifted)}
    diagnostic = data["diagnostic"]
    write(directory, "diagnostic-inputs.json", observations(diagnostic))
    diagnostic_tensor = backend.infer(model, tensor_values(backend, observations(diagnostic)))
    write(directory, "tensor-diagnostic.json", diagnostic_tensor)
    diagnostic_native = checked_native(binary, directory, "selected.json", "diagnostic-inputs.json",
                                       "native-diagnostic.json", request["rust_source"])
    diagnostic_error = parity(diagnostic_native, diagnostic_tensor)
    diagnostic_metrics = metrics(diagnostic_native, arm)
    restart_indices = [family * 96 + offset for family in range(4) for offset in range(2)]
    for index in restart_indices:
        name = f"restart-input-{index}.json"
        write(directory, name, observations([rows[index]]))
        extras = [str(directory / f"intermediate-{index}")]
        prefix = checked_native(binary, directory, "selected.json", name, f"prefix-{index}.json",
                                request["rust_source"], "persist", extras)
        resumed = checked_native(binary, directory, "selected.json", name, f"resumed-{index}.json",
                                 request["rust_source"], "resume", extras)
        original = receipt["rows"][index]
        if (prefix["rows"][0]["intermediate"] != original["intermediate"]
                or any(resumed["rows"][0][key] != original[key] for key in ("intermediate", "logits", "prediction"))):
            raise ContractError("representation differs after independent-process intermediate restart")
    presentations = steps * 6 + 3 * 96 + 2 * len(rows) + 2 * len(diagnostic) + 16
    if arm == "conditional":
        presentations += 2 * len(rows)
    if presentations > protocol["budget"]["max_case_presentations_per_run"]:
        raise ContractError("representation presentation admission exceeded")
    write(directory, "report.json", {"status": "completed", "arm": arm, "seed": seed, "steps": steps,
          "selected_step": selected["step"], "parameter_count": parameter_count(arm),
          "training_proxy_ops": training_proxy(arm, steps), "forward_scalar_ops": forward_ops(arm),
          "environment": environment, "validation_checkpoints": checkpoints, "losses": losses,
          "case_presentations": presentations, "results": results, "shifted": shifted_result,
          "diagnostic": {**diagnostic_summary(diagnostic, predictions(diagnostic_native)),
                         "metrics": diagnostic_metrics, "maximum_native_tensor_error": diagnostic_error},
          "restart_cases": len(restart_indices), "restart_passed": True,
          "fitting_validation_seconds": fitting_seconds, "peak_rss_bytes": peak_rss_bytes(),
          "elapsed_seconds": time.monotonic() - started,
          "measurement_scope": "Nominal model arithmetic is a proxy. Validation, evidence statistics, state transactions, parsing and serialization remain included in measured process time; sampled RSS is not an OS sandbox."})


def main() -> int:
    kind, directory = sys.argv[1], Path(sys.argv[2])
    protocol, request = read_json(directory / "protocol.json"), read_json(directory / "request.json")
    if kind == "preflight":
        preflight(directory, protocol, request)
    elif kind == "train":
        train(directory, protocol, request)
    else:
        raise ContractError("unknown representation worker mode")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
        raise SystemExit(1)
