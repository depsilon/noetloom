#!/usr/bin/env python3
"""Execute and replay the registered EXP-0003 read-allocation probe."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noetloom.allocation_contracts import validate_allocation_protocol
from noetloom.allocation_data import generate
from noetloom.allocation_worker import allocation_parity
from noetloom.contracts import ContractError, canonical_bytes, load_policy, read_json
from noetloom.learning_data import observations_only
from noetloom.learning_worker import check_native_identity, native, parity, score
from noetloom.storage import (RunLease, RunWriter, StorageError, default_cache, file_digest,
                              source_identity, storage_snapshot, tree_bytes, validate_cache)
import learning as learning_tools
import rust as rust_tools
from learning_setup import environment

PROTOCOL = ROOT / "experiments/EXP-0003/protocol.json"
PARENTS = ROOT / "experiments/EXP-0003/parents.json"
RESERVATION = 16 * 1024**2


def identity() -> dict:
    return {"python": source_identity(ROOT), "rust": rust_tools.rust_source(),
            "scripts": [{"path": str(path.relative_to(ROOT)), "sha256": file_digest(path)}
                        for path in sorted((ROOT / "scripts").glob("*.py"))],
            "protocol_sha256": file_digest(PROTOCOL), "parents_sha256": file_digest(PARENTS),
            "design_sha256": file_digest(ROOT / "experiments/EXP-0003/design.md")}


def parents(cache: Path) -> list[dict]:
    inventory = read_json(PARENTS)
    if inventory.get("schema_version") != "noetloom.allocation_parents.v1":
        raise ContractError("unsupported parent inventory")
    records = inventory["records"]
    if [row["seed"] for row in records] != read_json(PROTOCOL)["seeds"]:
        raise ContractError("parent seed inventory differs from registration")
    verified = []
    for row in records:
        if not re.fullmatch(r"learning-train-\d{8}T\d{6}Z-[0-9a-f]{8}", row["run_id"]):
            raise ContractError("parent run identity is not a bounded run name")
        directory = cache / row["run_id"]
        if file_digest(directory / "manifest.json") != row["manifest_sha256"]:
            raise ContractError("parent manifest identity differs")
        manifest = learning_tools.check_manifest(directory, current=False)
        checkpoint = read_json(directory / "selected.json")
        if file_digest(directory / "selected.json") != row["checkpoint_sha256"]:
            raise ContractError("parent checkpoint identity differs")
        if manifest["kind"] != "train" or manifest["arm"] != "dense" or checkpoint["arm"] != "dense" or checkpoint["seed"] != row["seed"] or checkpoint["step"] != row["selected_step"]:
            raise ContractError("parent arm, seed or selected-step identity differs")
        for name in ("protocol_sha256", "design_sha256"):
            if manifest["source"][name] != inventory[name]:
                raise ContractError("parent source provenance differs")
        verified.append({**row, "checkpoint_path": str(directory / "selected.json"),
                         "parent_source": manifest["source"],
                         "inherited_training_report_sha256": file_digest(directory / "report.json")})
    return verified


def check_manifest(directory: Path) -> dict:
    manifest = read_json(directory / "manifest.json", 1024**2)
    if manifest.get("status") != "passed" or manifest.get("schema_version") != "noetloom.allocation_run.v1":
        raise ContractError("incomplete or unsupported allocation run")
    if learning_tools.artifacts(directory) != manifest["artifacts"]:
        raise ContractError("allocation artifact inventory, bytes or hashes changed")
    if manifest["source"] != identity():
        raise ContractError("allocation source differs; use the committed original for replay")
    return manifest


def new_writer(cache: Path, kind: str, seconds: int = 120) -> RunWriter:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    return RunWriter(cache / ("allocation-" + kind + "-" + stamp), RESERVATION, seconds)


def refuse_existing_attempt(cache: Path, protocol: dict, seed: int) -> None:
    for path in cache.glob("allocation-train-*/request.json"):
        previous = read_json(path)
        if previous.get("seed") == seed and read_json(path.parent / "protocol.json") == protocol:
            raise ContractError("this registered seed already has an attempt; a new preflight cannot reset its budget")


def finish(writer: RunWriter, source: dict, binary: Path, binary_hash: str, policy: dict, details: dict) -> dict:
    writer.checkpoint()
    if identity() != source or file_digest(binary) != binary_hash:
        raise ContractError("allocation source or executable changed during work")
    manifest = {"schema_version": "noetloom.allocation_run.v1", "status": "passed", "source": source,
                "binary_sha256": binary_hash, "resource_policy": policy,
                "git_head_context": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                                      text=True, check=True, timeout=10).stdout.strip(),
                "artifacts": learning_tools.artifacts(writer.directory), **details}
    reserve = len(canonical_bytes(manifest)) + 65536
    if tree_bytes(writer.directory) + reserve > writer.max_bytes:
        raise StorageError("allocation completion marker exceeds output admission")
    storage_snapshot(writer.directory.parent, policy, reserve)
    writer.write_json("manifest.json", manifest)
    return {"status": "passed", "directory": str(writer.directory), "manifest_sha256": file_digest(writer.directory / "manifest.json")}


def execute(kind: str, admission: Path | None = None, seed: int | None = None) -> dict:
    if kind not in {"preflight", "train"}:
        raise ContractError("unsupported allocation execution mode")
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT)
    validate_allocation_protocol(protocol, policy)
    cache = validate_cache(default_cache(), ROOT)
    tooling, env = environment()
    env.update(PYTHONPATH=os.pathsep.join((str(tooling / "learning-python"), str(ROOT))),
               PYTHONNOUSERSITE="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    with RunLease(cache, policy, RESERVATION):
        inherited = parents(cache)
        compile_seconds = 0.0
        if kind == "preflight":
            _, rust_env = rust_tools.tooling_environment()
            rust_tools.check_tooling(tooling, policy["min_free_disk_bytes"], reserve=True)
            timer = time.monotonic()
            rust_tools.cargo(["build", "--release", "--example", "learning", "--locked"], rust_env, tooling, policy)
            compile_seconds = time.monotonic() - timer
        else:
            if admission is None or seed not in protocol["seeds"]:
                raise ContractError("allocation run needs admitted preflight and registered seed")
            admitted = check_manifest(admission)
            if admitted["kind"] != "preflight" or read_json(admission / "protocol.json") != protocol:
                raise ContractError("allocation admission is not the registered preflight")
            if read_json(admission / "data.json", 8 * 1024**2) != generate(protocol):
                raise ContractError("allocation data differs from frozen generation")
            if read_json(admission / "request.json")["parents"] != inherited:
                raise ContractError("parent evidence differs from preflight")
            refuse_existing_attempt(cache, protocol, seed)
        seconds = protocol["preflight"]["max_wall_seconds"] if kind == "preflight" else protocol["budget"]["max_wall_seconds_per_run"]
        writer = new_writer(cache, kind, seconds)
        writer.max_bytes = protocol["preflight"]["max_output_bytes"] if kind == "preflight" else protocol["budget"]["max_output_bytes_per_run"]
        try:
            if kind == "preflight":
                # Preserve the exact executable, so future builds cannot erase replay's binary.
                binary = writer.directory / "native-learning"
                shutil.copy2(tooling / "cargo-target/release/examples/learning", binary)
            else:
                binary = admission / "native-learning"
                if file_digest(binary) != admitted["binary_sha256"]:
                    raise ContractError("allocation native executable differs from preflight")
            source, binary_hash = identity(), file_digest(binary)
            writer.write_json("protocol.json", protocol)
            writer.write_json("request.json", {"kind": kind, "seed": seed, "binary": str(binary),
                              "rust_source": source["rust"], "parents": inherited,
                              "admission": str(admission) if admission else None,
                              "admission_manifest_sha256": file_digest(admission / "manifest.json") if admission else None})
            monitor = learning_tools.supervised([sys.executable, "-B", "-m", "noetloom.allocation_worker", kind, str(writer.directory)],
                        env, writer.directory, policy, seconds, protocol["budget"]["max_peak_rss_bytes"], writer.max_bytes)
            report = read_json(writer.directory / ("preflight.json" if kind == "preflight" else "report.json"))
            if report["peak_rss_bytes"] > protocol["budget"]["max_peak_rss_bytes"]:
                raise StorageError("allocation worker final peak RSS exceeds admission")
            if inherited != parents(cache):
                raise ContractError("parent evidence changed during allocation work")
            return finish(writer, source, binary, binary_hash, policy,
                          {"kind": kind, "seed": seed, "monitor": monitor, "compile_seconds": compile_seconds,
                           "admission": str(admission) if admission else None})
        except Exception as error:
            try:
                writer.write_json("failure.json", {"status": "failed", "error": str(error)})
            except (OSError, StorageError):
                pass
            raise


def validate_parameters(directory: Path, parent: dict, seed: int) -> None:
    if read_json(directory / "parent.json") != parent or parent["seed"] != seed:
        raise ContractError("run parent parameters differ from frozen parent")
    gate = read_json(directory / "selected-gate.json")
    report = read_json(directory / "report.json")
    if read_json(directory / f"gate-step-{report['selected_step']}.json") != gate:
        raise ContractError("selected gate differs from its recorded checkpoint")
    if report["selected_step"] != min(report["validation_checkpoints"], key=lambda row: (row["objective"], row["step"]))["step"]:
        raise ContractError("selected gate violates registered validation selection")
    for arm in ("adaptive", "top_one", "dense"):
        expected = copy.deepcopy(parent)
        if arm == "adaptive":
            expected.update(schema_version="noetloom.cell_parameters.v2", arm="adaptive", gate=gate)
        else:
            expected["arm"] = "selective" if arm == "top_one" else "dense"
        if read_json(directory / f"parameters-{arm}.json") != expected:
            raise ContractError("policy artifact changes frozen parent or selected gate")


def verify(directory: Path) -> dict:
    original = check_manifest(directory)
    if original["kind"] != "train":
        raise ContractError("allocation replay expects a completed seed run")
    request, report = read_json(directory / "request.json"), read_json(directory / "report.json")
    admission = Path(request["admission"])
    admitted = check_manifest(admission)
    if admitted["kind"] != "preflight" or file_digest(admission / "manifest.json") != request["admission_manifest_sha256"]:
        raise ContractError("allocation admission changed")
    policy, protocol = load_policy(ROOT), read_json(PROTOCOL)
    validate_allocation_protocol(protocol, policy)
    if read_json(directory / "protocol.json") != protocol or read_json(admission / "protocol.json") != protocol:
        raise ContractError("replay protocol differs from registration")
    data = generate(protocol)
    if read_json(admission / "data.json", 8 * 1024**2) != data:
        raise ContractError("allocation replay data differs from registered generator")
    rows = [row for family in protocol["data"]["test_families"] for row in data["datasets"][f"test_{family}"]]
    if json.loads((directory / "observations.json").read_bytes()) != observations_only(rows):
        raise ContractError("allocation observations differ from frozen data")
    cache = validate_cache(default_cache(), ROOT)
    inherited = parents(cache)
    if request["parents"] != inherited:
        raise ContractError("run parent inventory differs")
    if not (request["seed"] == report["seed"] == original["seed"]):
        raise ContractError("allocation seed identities disagree")
    parent = next(row for row in inherited if row["seed"] == request["seed"])
    validate_parameters(directory, read_json(Path(parent["checkpoint_path"])), request["seed"])
    binary = Path(request["binary"])
    if binary != admission / "native-learning" or file_digest(binary) != original["binary_sha256"]:
        raise ContractError("allocation replay binary differs")
    with RunLease(cache, policy, RESERVATION):
        writer = new_writer(cache, "verify")
        try:
            shutil.copyfile(directory / "observations.json", writer.directory / "observations.json")
            source, errors = identity(), {}
            for arm in protocol["arms"]:
                name = f"parameters-{arm}.json"
                shutil.copyfile(directory / name, writer.directory / name)
                receipt = native(binary, writer.directory, name, "observations.json", f"replayed-{arm}.json")
                check_native_identity(receipt, writer.directory / name, writer.directory / "observations.json", source["rust"])
                tensor = read_json(directory / f"tensor-{arm}.json", 8 * 1024**2)
                errors[arm] = allocation_parity(receipt, rows, tensor) if arm == "adaptive" else parity(receipt, rows, tensor)
                actual, expected = score(receipt, rows), copy.deepcopy(report["arms"][arm]["scored"])
                actual["native_metrics"].pop("elapsed_ns")
                expected["native_metrics"].pop("elapsed_ns")
                if actual != expected:
                    raise ContractError("allocation replay scores or operation counts differ")
                for family in protocol["data"]["test_families"]:
                    actual_bytes = sum(result["metrics"]["payload_read_bytes"] for result in receipt["results"]
                                       if result["id"].startswith(f"test_{family}-"))
                    if actual_bytes != report["arms"][arm]["family_payload_bytes"][f"test_{family}"]:
                        raise ContractError("allocation family cost report differs")
            writer.write_json("verification.json", {"status": "passed", "run": str(directory),
                "manifest_sha256": file_digest(directory / "manifest.json"), "queries_replayed": len(rows) * 8 * 3,
                "maximum_logit_errors": errors,
                "proof_scope": "Frozen-parent/gate inference and scoring replay; no independent retraining or attestation of historical timings."})
            return finish(writer, source, binary, original["binary_sha256"], policy, {"kind": "verification", "run": str(directory)})
        except Exception as error:
            writer.write_json("failure.json", {"status": "failed", "error": str(error)})
            raise


def equal_payload_control(report: dict) -> dict:
    families = report["arms"]["adaptive"]["scored"]["families"]
    results = {}
    for family in families:
        arms = report["arms"]
        sparse, dense, adaptive = (arms[arm]["family_payload_bytes"][family] for arm in ("top_one", "dense", "adaptive"))
        if not sparse <= adaptive <= dense or sparse == dense:
            raise ContractError("allocation cost is outside fixed-policy endpoints")
        rate = (adaptive - sparse) / (dense - sparse)
        expected = (1 - rate) * arms["top_one"]["scored"]["families"][family]["accuracy"] + rate * arms["dense"]["scored"]["families"][family]["accuracy"]
        results[family] = {"dense_probability": rate, "expected_accuracy": expected,
                           "matched_payload_bytes": adaptive}
    count = sum(row["queries"] for row in families.values())
    return {"families": results, "expected_accuracy": sum(results[name]["expected_accuracy"] * row["queries"]
            for name, row in families.items()) / count}


def seed_interval(values: list[float]) -> dict:
    if len(values) != 5:
        raise ContractError("registered interval requires five independent seeds")
    mean = statistics.mean(values)
    half = 2.7764451052 * statistics.stdev(values) / math.sqrt(5)
    return {"differences_by_seed": values, "mean": mean, "low": mean - half, "high": mean + half}


def summarize(admission: Path) -> dict:
    check_manifest(admission)
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT)
    cache = validate_cache(default_cache(), ROOT)
    reports, run_identities = {}, []
    for path in sorted(cache.glob("allocation-train-*/request.json")):
        request = read_json(path)
        if request.get("admission") != str(admission):
            continue
        check_manifest(path.parent)  # A failed seed remains an attempt; it cannot disappear.
        report = read_json(path.parent / "report.json")
        if report["seed"] in reports:
            raise ContractError("duplicate allocation seed attempt")
        verified = []
        for verification in cache.glob("allocation-verify-*/verification.json"):
            value = read_json(verification)
            if value.get("run") == str(path.parent) and value.get("manifest_sha256") == file_digest(path.parent / "manifest.json"):
                check_manifest(verification.parent)
                verified.append({"directory": str(verification.parent), "manifest_sha256": file_digest(verification.parent / "manifest.json")})
        if not verified:
            raise ContractError("allocation seed has no completed independent replay")
        reports[report["seed"]] = report
        run_identities.append({"seed": report["seed"], "directory": str(path.parent),
                               "manifest_sha256": file_digest(path.parent / "manifest.json"), "verifications": verified})
    if set(reports) != set(protocol["seeds"]):
        raise ContractError("incomplete allocation campaign cannot yield a research decision")
    ordered = [reports[seed] for seed in protocol["seeds"]]
    controls = [equal_payload_control(report) for report in ordered]
    def accuracy(report: dict, arm: str) -> float:
        return report["arms"][arm]["scored"]["accuracy"]
    comparisons = {
        "dense": seed_interval([accuracy(r, "adaptive") - accuracy(r, "dense") for r in ordered]),
        "equal_payload_random": seed_interval([accuracy(r, "adaptive") - c["expected_accuracy"] for r, c in zip(ordered, controls)]),
    }
    arm_results = {arm: {"accuracy": statistics.mean(accuracy(r, arm) for r in ordered),
                 "families": {family: statistics.mean(r["arms"][arm]["scored"]["families"][f"test_{family}"]["accuracy"] for r in ordered)
                              for family in protocol["data"]["test_families"]},
                 "seeds": [{"seed": r["seed"], **r["arms"][arm]} for r in ordered]}
                 for arm in protocol["arms"]}
    def metric_ratio(key: str) -> float:
        return sum(r["arms"]["adaptive"]["scored"]["native_metrics"][key] for r in ordered) / sum(r["arms"]["dense"]["scored"]["native_metrics"][key] for r in ordered)
    payload_ratio, nominal_ratio = metric_ratio("payload_read_bytes"), metric_ratio("nominal_scalar_ops")
    continuation_rates = [r["arms"]["adaptive"]["scored"]["native_metrics"]["continued_queries"] / r["arms"]["adaptive"]["scored"]["queries"] for r in ordered]
    acceptance = protocol["acceptance"]
    gates = {
        "accuracy": arm_results["adaptive"]["accuracy"] >= acceptance["all_family_accuracy"],
        "worst_family": min(arm_results["adaptive"]["families"].values()) >= acceptance["minimum_family_accuracy"],
        "dense_noninferiority": comparisons["dense"]["low"] >= acceptance["dense_difference_ci_low"],
        "family_noninferiority": all(arm_results["adaptive"]["families"][family] - arm_results["dense"]["families"][family] >= acceptance["minimum_family_dense_difference"] for family in protocol["data"]["test_families"]),
        "input_dependence": comparisons["equal_payload_random"]["low"] > acceptance["random_difference_ci_low"],
        "payload_read_ratio": payload_ratio <= acceptance["max_payload_read_ratio"],
        "total_nominal_work": nominal_ratio <= acceptance["max_nominal_scalar_ratio"],
        "variable_allocation": all(acceptance["minimum_continue_rate"] <= rate <= acceptance["maximum_continue_rate"] for rate in continuation_rates),
    }
    with RunLease(cache, policy, RESERVATION):
        writer = new_writer(cache, "summary")
        summary = {"status": "completed", "decision": "retain" if all(gates.values()) else "reject_registered_configuration",
                   "gates": gates, "arms": arm_results, "paired_seed_intervals": comparisons,
                   "payload_read_ratio": payload_ratio, "nominal_scalar_ratio": nominal_ratio,
                   "continuation_rates": continuation_rates,
                   "equal_payload_random_controls": [{"seed": seed, **control} for seed, control in zip(protocol["seeds"], controls)],
                   "training_runs": run_identities, "scope": protocol["claim_boundary"], "speed_claim": False}
        writer.write_json("summary.json", summary)
        binary = admission / "native-learning"
        result = finish(writer, identity(), binary, file_digest(binary), policy, {"kind": "summary", "admission": str(admission)})
        result["decision"] = summary["decision"]
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "run", "campaign", "verify", "summarize"))
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            result = execute("preflight")
        elif args.command == "verify":
            if args.run is None:
                raise ContractError("verify requires --run")
            result = verify(args.run.resolve())
        else:
            if args.admission is None:
                raise ContractError("allocation execution requires --admission")
            admission = args.admission.resolve()
            if args.command == "run":
                result = execute("train", admission, args.seed)
            elif args.command == "campaign":
                for seed in read_json(PROTOCOL)["seeds"]:
                    result = execute("train", admission, seed)
                    print(json.dumps({**result, "seed": seed}), flush=True)
                    print(json.dumps({**verify(Path(result["directory"])), "action": "verification"}), flush=True)
                result = summarize(admission)
            else:
                result = summarize(admission)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ContractError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
