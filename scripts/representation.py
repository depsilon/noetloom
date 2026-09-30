#!/usr/bin/env python3
"""Admit, execute and independently replay the single registered EXP-0004 experiment."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noetloom.contracts import ContractError, canonical_bytes, load_policy, read_json
from noetloom.representation_common import ARMS, forward_ops, parameter_count, training_proxy, validate_parameters
from noetloom.representation_contracts import validate_representation_protocol
from noetloom.representation_data import FAMILIES, generate, observations, score
from noetloom.representation_worker import checked_native, diagnostic_summary, metrics, parity, predictions
from noetloom.storage import (RunLease, RunWriter, StorageError, default_cache, file_digest,
                              source_identity, storage_snapshot, tree_bytes, validate_cache)
import learning as learning_tools
import rust as rust_tools
from learning_setup import environment

PROTOCOL = ROOT / "experiments/EXP-0004/protocol.json"
RESERVATION = 32 * 1024**2


def identity() -> dict:
    return {"python": source_identity(ROOT), "rust": rust_tools.rust_source(),
            "scripts": [{"path": str(path.relative_to(ROOT)), "sha256": file_digest(path)}
                        for path in sorted((ROOT / "scripts").glob("*.py"))],
            "protocol_sha256": file_digest(PROTOCOL),
            "design_sha256": file_digest(ROOT / "experiments/EXP-0004/design.md")}


def check_manifest(directory: Path) -> dict:
    manifest = read_json(directory / "manifest.json", 1024**2)
    if manifest.get("schema_version") != "noetloom.representation_run.v1" or manifest.get("status") != "passed":
        raise ContractError("incomplete or unsupported representation run")
    if learning_tools.artifacts(directory) != manifest["artifacts"]:
        raise ContractError("representation artifact inventory, bytes or hashes differ")
    if manifest["source"] != identity():
        raise ContractError("representation source differs; replay with the preserved original commit")
    return manifest


def new_writer(cache: Path, kind: str, seconds: int = 120) -> RunWriter:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    return RunWriter(cache / ("representation-" + kind + "-" + stamp), RESERVATION, seconds)


def attempts(cache: Path) -> dict[tuple[str, int], Path]:
    found = {}
    for path in sorted(cache.glob("representation-train-*/request.json")):
        request = read_json(path)
        registered = read_json(path.parent / "protocol.json")
        if registered.get("id") != "EXP-0004":
            continue
        key = (request.get("arm"), request.get("seed"))
        if key in found:
            raise ContractError("duplicate EXP-0004 arm/seed attempts exist; cannot hide an attempt")
        found[key] = path.parent
    return found


def refuse_existing_attempt(cache: Path, protocol: dict, arm: str, seed: int) -> None:
    previous = attempts(cache)
    if (arm, seed) in previous:
        raise ContractError("this registered arm/seed already has an attempt; source or admission changes cannot reset it")
    if len(previous) >= protocol["budget"]["max_training_attempts"]:
        raise ContractError("registered training-attempt ceiling reached")


def finish(writer: RunWriter, source: dict, binary: Path, binary_hash: str, policy: dict, details: dict) -> dict:
    writer.checkpoint()
    if identity() != source or file_digest(binary) != binary_hash:
        raise ContractError("representation source or executable changed during execution")
    manifest = {"schema_version": "noetloom.representation_run.v1", "status": "passed", "source": source,
                "binary_sha256": binary_hash, "resource_policy": policy,
                "git_head_context": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                    capture_output=True, text=True, check=True, timeout=10).stdout.strip(),
                "artifacts": learning_tools.artifacts(writer.directory), **details}
    reserve = len(canonical_bytes(manifest)) + 65536
    if tree_bytes(writer.directory) + reserve > writer.max_bytes:
        raise StorageError("representation completion marker exceeds admission")
    storage_snapshot(writer.directory.parent, policy, reserve)
    writer.write_json("manifest.json", manifest)
    return {"status": "passed", "directory": str(writer.directory),
            "manifest_sha256": file_digest(writer.directory / "manifest.json")}


def failure(writer: RunWriter, error: Exception) -> None:
    # If even a failure note cannot fit, leave the uncompleted directory and original error.
    try:
        writer.write_json("failure.json", {"status": "failed", "error": str(error)})
    except (StorageError, OSError):
        pass


def execute(kind: str, admission: Path | None = None, arm: str | None = None, seed: int | None = None) -> dict:
    if kind not in {"preflight", "train"}:
        raise ContractError("unsupported representation execution mode")
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT)
    validate_representation_protocol(protocol, policy)
    cache = validate_cache(default_cache(), ROOT)
    tooling, env = environment()
    env.update(PYTHONPATH=os.pathsep.join((str(tooling / "learning-python"), str(ROOT))),
               PYTHONNOUSERSITE="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    with RunLease(cache, policy, RESERVATION):
        compile_seconds = 0.0
        if kind == "preflight":
            _, rust_env = rust_tools.tooling_environment()
            rust_tools.check_tooling(tooling, policy["min_free_disk_bytes"], reserve=True)
            timer = time.monotonic()
            rust_tools.cargo(["build", "--release", "--example", "representation", "--locked"], rust_env, tooling, policy)
            compile_seconds = time.monotonic() - timer
        else:
            if admission is None or arm not in protocol["arms"] or seed not in protocol["seeds"]:
                raise ContractError("training requires admitted preflight, arm and seed")
            admitted = check_manifest(admission)
            if admitted["kind"] != "preflight" or read_json(admission / "protocol.json") != protocol:
                raise ContractError("training admission is not this registered preflight")
            if read_json(admission / "data.json", 8 * 1024**2) != generate(protocol):
                raise ContractError("frozen representation data differs from generation")
            refuse_existing_attempt(cache, protocol, arm, seed)
        seconds = protocol["preflight"]["max_wall_seconds"] if kind == "preflight" else protocol["budget"]["max_wall_seconds_per_run"]
        writer = new_writer(cache, kind, seconds)
        writer.max_bytes = protocol["preflight"]["max_output_bytes"] if kind == "preflight" else protocol["budget"]["max_output_bytes_per_run"]
        try:
            if kind == "preflight":
                binary = writer.directory / "native-representation"
                shutil.copy2(tooling / "cargo-target/release/examples/representation", binary)
            else:
                binary = admission / "native-representation"
                if file_digest(binary) != admitted["binary_sha256"]:
                    raise ContractError("native executable differs from representation preflight")
            source, binary_hash = identity(), file_digest(binary)
            writer.write_json("protocol.json", protocol)
            writer.write_json("request.json", {"kind": kind, "arm": arm, "seed": seed, "binary": str(binary),
                "rust_source": source["rust"], "admission": str(admission) if admission else None,
                "admission_manifest_sha256": file_digest(admission / "manifest.json") if admission else None})
            monitor = learning_tools.supervised([sys.executable, "-B", "-m", "noetloom.representation_worker", kind,
                str(writer.directory)], env, writer.directory, policy, seconds,
                protocol["budget"]["max_peak_rss_bytes"], writer.max_bytes)
            report = read_json(writer.directory / ("preflight.json" if kind == "preflight" else "report.json"))
            if report["peak_rss_bytes"] > protocol["budget"]["max_peak_rss_bytes"]:
                raise StorageError("worker final peak RSS exceeds admission")
            return finish(writer, source, binary, binary_hash, policy,
                          {"kind": kind, "arm": arm, "seed": seed, "monitor": monitor,
                           "compile_seconds": compile_seconds, "admission": str(admission) if admission else None})
        except Exception as error:
            failure(writer, error)
            raise


def validate_selection(directory: Path, protocol: dict, manifest: dict, admitted_steps: int) -> dict:
    artifact, report = read_json(directory / "selected.json"), read_json(directory / "report.json")
    validate_parameters(artifact)
    if manifest["kind"] != "train" or (artifact["arm"], artifact["seed"]) != (manifest["arm"], manifest["seed"]):
        raise ContractError("selected parameters differ from arm/seed identity")
    if (report["arm"], report["seed"], report["steps"]) != (artifact["arm"], artifact["seed"], admitted_steps):
        raise ContractError("reported identity or update count differs from admission")
    checkpoints = report["validation_checkpoints"]
    expected_steps = [int(report["steps"] * fraction) for fraction in protocol["training"]["validation_fractions"]]
    if report["steps"] not in protocol["training"]["candidate_steps"] or [row["step"] for row in checkpoints] != expected_steps:
        raise ContractError("validation checkpoint opportunities differ")
    if any(type(row["cross_entropy"]) not in (int, float) or not math.isfinite(row["cross_entropy"]) for row in checkpoints):
        raise ContractError("invalid checkpoint-selection objective")
    expected = min(checkpoints, key=lambda row: (row["cross_entropy"], row["step"]))["step"]
    if (artifact["step"] != expected or report["selected_step"] != expected
            or artifact != read_json(directory / f"checkpoint-{expected}.json")):
        raise ContractError("selected artifact differs from registered checkpoint rule")
    if (report["parameter_count"] != parameter_count(artifact["arm"])
            or report["training_proxy_ops"] != training_proxy(artifact["arm"], report["steps"])):
        raise ContractError("reported fitting capacity or work differs")
    expected_presentations = admitted_steps * 6 + 288 + 768 + 576 + 16
    if artifact["arm"] == "conditional":
        expected_presentations += 768
    if (report["case_presentations"] != expected_presentations
            or expected_presentations > protocol["budget"]["max_case_presentations_per_run"]
            or report["training_proxy_ops"] > protocol["budget"]["max_training_proxy_ops"]
            or report["forward_scalar_ops"] != forward_ops(artifact["arm"])
            or report["forward_scalar_ops"] > protocol["budget"]["max_forward_scalar_ops"]):
        raise ContractError("reported representation work exceeds or differs from admission")
    return artifact


def deterministic(receipt: dict) -> dict:
    return {key: value for key, value in receipt.items() if key != "elapsed_seconds" and not key.startswith("driver_")}


def verify(directory: Path) -> dict:
    original = check_manifest(directory)
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT)
    validate_representation_protocol(protocol, policy)
    request = read_json(directory / "request.json")
    admission = Path(request["admission"])
    admitted = check_manifest(admission)
    if request["admission_manifest_sha256"] != file_digest(admission / "manifest.json"):
        raise ContractError("run admission identity differs")
    artifact = validate_selection(directory, protocol, original, read_json(admission / "preflight.json")["selected_steps"])
    data = generate(protocol)
    if data != read_json(admission / "data.json", 8 * 1024**2):
        raise ContractError("replay data differs from frozen generation")
    if (read_json(directory / "inputs.json") != observations(data["test"])
            or read_json(directory / "diagnostic-inputs.json") != observations(data["diagnostic"])):
        raise ContractError("recorded observations differ from regenerated fields")
    binary = admission / "native-representation"
    if file_digest(binary) != original["binary_sha256"] or original["binary_sha256"] != admitted["binary_sha256"]:
        raise ContractError("replay binary differs from admission")
    cache = validate_cache(default_cache(), ROOT)
    with RunLease(cache, policy, RESERVATION):
        writer = new_writer(cache, "verify", protocol["budget"]["max_wall_seconds_per_run"])
        writer.max_bytes = protocol["budget"]["max_output_bytes_per_run"]
        source, errors, replayed = identity(), {}, 0
        try:
            writer.write_json("protocol.json", protocol)
            writer.write_json("parameters.json", artifact)
            results = [("ordinary", "inputs.json", "native.json", "tensor.json", data["test"], 0),
                       ("diagnostic", "diagnostic-inputs.json", "native-diagnostic.json", "tensor-diagnostic.json", data["diagnostic"], 0)]
            if artifact["arm"] == "conditional":
                results.append(("shifted", "inputs.json", "native-shifted.json", "tensor-shifted.json", data["test"], 96))
            report = read_json(directory / "report.json")
            for name, _, native_file, tensor_file, rows, group in results:
                input_file = f"{name}-inputs.json"
                writer.write_json(input_file, observations(rows))
                receipt = checked_native(binary, writer.directory, "parameters.json", input_file, f"{name}-native.json",
                    source["rust"], extras=[str(group)])
                original_receipt = read_json(directory / native_file, 8 * 1024**2)
                if deterministic(receipt) != deterministic(original_receipt):
                    raise ContractError("fresh native replay differs from original evidence")
                errors[name] = parity(receipt, read_json(directory / tensor_file, 8 * 1024**2))
                fresh_metrics = metrics(receipt, artifact["arm"], bool(group))
                if name == "diagnostic":
                    expected = diagnostic_summary(rows, predictions(receipt))
                    if any(report["diagnostic"][key] != value for key, value in expected.items()):
                        raise ContractError("replayed diagnostic differs from report")
                else:
                    key = "shifted" if group else "results"
                    if report[key]["scored"] != score(rows, predictions(receipt)):
                        raise ContractError("replayed scoring differs from report")
                reported_metrics = report["diagnostic" if name == "diagnostic" else ("shifted" if group else "results")]["metrics"]
                def logical(value: dict) -> dict:
                    return {k: v for k, v in value.items() if not k.endswith("seconds") and "rss" not in k}
                if logical(fresh_metrics) != logical(reported_metrics):
                    raise ContractError("replayed resource accounting differs from report")
                replayed += len(rows)
                writer.checkpoint()
            # Recompute every selection objective from exported checkpoints and raw validation fields.
            writer.write_json("validation-inputs.json", observations(data["validation"]))
            validation_errors = []
            for checkpoint in report["validation_checkpoints"]:
                name = f"checkpoint-{checkpoint['step']}.json"
                parameters = read_json(directory / name)
                validate_parameters(parameters)
                if (parameters["arm"], parameters["seed"], parameters["step"]) != (artifact["arm"], artifact["seed"], checkpoint["step"]):
                    raise ContractError("validation checkpoint identity differs")
                writer.write_json(name, parameters)
                receipt = checked_native(binary, writer.directory, name, "validation-inputs.json",
                    f"validation-{checkpoint['step']}.json", source["rust"])
                losses = []
                for row, case in zip(receipt["rows"], data["validation"]):
                    logits, target = row["logits"], case["expected"]
                    largest = max(logits)
                    losses.append(largest + math.log(sum(math.exp(x - largest) for x in logits)) - logits[target])
                if len(losses) != len(data["validation"]):
                    raise ContractError("validation replay omitted cases")
                error = abs(statistics.mean(losses) - checkpoint["cross_entropy"])
                if error > protocol["acceptance"]["absolute_parity_tolerance"]:
                    raise ContractError("native validation replay differs from selection objective")
                validation_errors.append({"step": checkpoint["step"], "absolute_error": error})
                replayed += len(losses)
                writer.checkpoint()
            # Read original intermediate state in a fresh process; never write into the source run.
            original_native = read_json(directory / "native.json", 8 * 1024**2)
            for index in [family * 96 + offset for family in range(4) for offset in range(2)]:
                name = f"restart-input-{index}.json"
                expected_input = observations([data["test"][index]])
                if read_json(directory / name) != expected_input:
                    raise ContractError("restart input differs from frozen field")
                writer.write_json(name, expected_input)
                resumed = checked_native(binary, writer.directory, "parameters.json", name, f"resumed-{index}.json",
                    source["rust"], "resume", [str(directory / f"intermediate-{index}")])
                if any(resumed["rows"][0][key] != original_native["rows"][index][key]
                       for key in ("intermediate", "logits", "prediction")):
                    raise ContractError("retained intermediate does not replay")
                replayed += 1
            check_manifest(directory)
            writer.write_json("verification.json", {"status": "passed", "run": str(directory),
                "manifest_sha256": file_digest(directory / "manifest.json"), "cases_replayed": replayed,
                "maximum_native_tensor_errors": errors,
                "validation_objective_replay": validation_errors,
                "proof_scope": "Independent native inference, scoring, intervention and retained-state replay; no independent retraining or attestation of historical timings."})
            return finish(writer, source, binary, original["binary_sha256"], policy,
                          {"kind": "verification", "run": str(directory), "admission": str(admission)})
        except Exception as error:
            failure(writer, error)
            raise


def seed_interval(values: list[float]) -> dict:
    if len(values) != 5 or any(not math.isfinite(x) for x in values):
        raise ContractError("interval requires five finite paired seed differences")
    mean = statistics.mean(values)
    half = 2.7764451052 * statistics.stdev(values) / math.sqrt(5)
    return {"differences_by_seed": values, "mean": mean, "low": mean - half, "high": mean + half}


def verified_records(directory: Path, cache: Path) -> list[dict]:
    matches = []
    for path in cache.glob("representation-verify-*/verification.json"):
        value = read_json(path)
        if value.get("run") == str(directory) and value.get("manifest_sha256") == file_digest(directory / "manifest.json"):
            check_manifest(path.parent)
            matches.append({"directory": str(path.parent), "manifest_sha256": file_digest(path.parent / "manifest.json"),
                            "cases_replayed": value["cases_replayed"]})
    return matches


def aggregate(protocol: dict, reports: dict[tuple[str, int], dict]) -> dict:
    expected = {(arm, seed) for arm in protocol["arms"] for seed in protocol["seeds"]}
    if set(reports) != expected:
        raise ContractError("incomplete representation campaign cannot yield a research decision")
    transfer = FAMILIES[1:]
    def transfer_accuracy(report: dict, shifted: bool = False) -> float:
        result = report["shifted" if shifted else "results"]["scored"]
        return statistics.mean(result[family]["accuracy"] for family in transfer)
    def ordered(arm: str) -> list[dict]:
        return [reports[(arm, seed)] for seed in protocol["seeds"]]
    arms = {arm: {"base_accuracy": statistics.mean(r["results"]["scored"]["base"]["accuracy"] for r in ordered(arm)),
                  "transfer_accuracy": statistics.mean(transfer_accuracy(r) for r in ordered(arm)),
                  "family_accuracy": {family: statistics.mean(r["results"]["scored"][family]["accuracy"] for r in ordered(arm)) for family in FAMILIES},
                  "parameters": parameter_count(arm), "forward_scalar_ops": forward_ops(arm),
                  "seeds": [{"seed": r["seed"], "selected_step": r["selected_step"],
                             "base_accuracy": r["results"]["scored"]["base"]["accuracy"],
                             "transfer_accuracy": transfer_accuracy(r), "training_proxy_ops": r["training_proxy_ops"],
                             "case_presentations": r["case_presentations"], "results": r["results"],
                             "diagnostic": r["diagnostic"], "fitting_validation_seconds": r["fitting_validation_seconds"],
                             "peak_rss_bytes": r["peak_rss_bytes"]} for r in ordered(arm)]}
            for arm in protocol["arms"]}
    conditional = ordered("conditional")
    intervals = {control: seed_interval([transfer_accuracy(c) - transfer_accuracy(r)
                  for c, r in zip(conditional, ordered(control))]) for control in protocol["arms"] if control != "conditional"}
    intervals["shifted"] = seed_interval([transfer_accuracy(r) - transfer_accuracy(r, True) for r in conditional])
    acceptance = protocol["acceptance"]
    agreement = statistics.mean(r["diagnostic"]["all_three_agreement"] for r in conditional)
    gates = {
        "base_accuracy": arms["conditional"]["base_accuracy"] >= acceptance["base_accuracy"],
        "transfer_accuracy": arms["conditional"]["transfer_accuracy"] >= acceptance["transfer_accuracy"],
        "minimum_transfer_family": min(arms["conditional"]["family_accuracy"][family] for family in transfer) >= acceptance["minimum_transfer_family_accuracy"],
        "minimum_seed_transfer": all(transfer_accuracy(r) >= acceptance["minimum_seed_transfer_accuracy"] for r in conditional),
        "beats_all_controls": all(intervals[control]["low"] > acceptance["control_difference_ci_low"] for control in protocol["arms"] if control != "conditional"),
        "conditional_transport_matters": intervals["shifted"]["low"] > acceptance["intervention_difference_ci_low"],
        "cross_surface_agreement": agreement >= acceptance["cross_surface_agreement"],
        "larger_control_covers_capacity_and_work": parameter_count("fixed_large") > parameter_count("conditional")
            and forward_ops("fixed_large") > forward_ops("conditional") and all(
            b["training_proxy_ops"] >= c["training_proxy_ops"] and b["steps"] == c["steps"] for b, c in zip(ordered("fixed_large"), conditional)),
        "complete_verified_acquisition": all(r["restart_passed"] and r["restart_cases"] == 8
            and r["peak_rss_bytes"] <= protocol["budget"]["max_peak_rss_bytes"] for r in reports.values()),
    }
    acquisition_failed = all(arms[arm]["base_accuracy"] < acceptance["acquisition_floor"] for arm in protocol["arms"])
    return {"status": "completed", "decision": "retain" if all(gates.values()) else "reject_registered_configuration",
            "comparison_status": "inconclusive_task_acquisition_failed" if acquisition_failed else "completed_bounded_comparison",
            "gates": gates, "arms": arms, "paired_seed_intervals": intervals,
            "conditional_cross_surface_agreement": agreement,
            "conditional_shifted_results": [{"seed": r["seed"], **r["shifted"]} for r in conditional],
            "scope": protocol["claim_boundary"], "speed_claim": False}


def summarize(admission: Path) -> dict:
    check_manifest(admission)
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT)
    cache = validate_cache(default_cache(), ROOT)
    reports, records = {}, []
    for (arm, seed), directory in attempts(cache).items():
        request = read_json(directory / "request.json")
        if request["admission"] != str(admission):
            raise ContractError("registered attempts span different admissions; cannot choose a favorable campaign")
        manifest = check_manifest(directory)
        validate_selection(directory, protocol, manifest, read_json(admission / "preflight.json")["selected_steps"])
        verified = verified_records(directory, cache)
        if not verified:
            raise ContractError("representation run has no completed independent replay")
        reports[(arm, seed)] = read_json(directory / "report.json")
        records.append({"arm": arm, "seed": seed, "directory": str(directory),
                        "manifest_sha256": file_digest(directory / "manifest.json"), "verifications": verified})
    summary = aggregate(protocol, reports)
    summary["training_runs"] = records
    with RunLease(cache, policy, RESERVATION):
        writer = new_writer(cache, "summary")
        writer.write_json("summary.json", summary)
        binary = admission / "native-representation"
        result = finish(writer, identity(), binary, file_digest(binary), policy, {"kind": "summary", "admission": str(admission)})
        return {**result, "decision": summary["decision"], "comparison_status": summary["comparison_status"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    for name in ("run", "campaign", "summarize"):
        child = sub.add_parser(name)
        child.add_argument("--admission", type=Path, required=True)
        if name == "run":
            child.add_argument("--arm", choices=ARMS, required=True)
            child.add_argument("--seed", type=int, required=True)
    sub.add_parser("verify").add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "preflight":
        result = execute("preflight")
    elif args.command == "run":
        result = execute("train", args.admission.resolve(), args.arm, args.seed)
    elif args.command == "verify":
        result = verify(args.run.resolve())
    elif args.command == "summarize":
        result = summarize(args.admission.resolve())
    else:
        admission, protocol = args.admission.resolve(), read_json(PROTOCOL)
        cache = validate_cache(default_cache(), ROOT)
        for seed in protocol["seeds"]:
            for arm in protocol["arms"]:
                previous = attempts(cache).get((arm, seed))
                if previous is None:
                    completed = execute("train", admission, arm, seed)
                    previous = Path(completed["directory"])
                else:
                    check_manifest(previous)  # Failed attempts are never silently repeated.
                    if read_json(previous / "request.json")["admission"] != str(admission):
                        raise ContractError("existing attempt belongs to another admission")
                if not verified_records(previous, cache):
                    verify(previous)
                print(json.dumps({"arm": arm, "seed": seed, "status": "trained_and_replayed"}), flush=True)
        result = summarize(admission)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, StorageError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
        raise SystemExit(2)
