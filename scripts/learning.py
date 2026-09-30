#!/usr/bin/env python3
"""Admit, execute, verify, and summarize the frozen EXP-0002 experiment."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noetloom.contracts import ContractError, canonical_bytes, load_policy, read_json
from noetloom.learning_contracts import validate_learning_protocol
from noetloom.learning_data import generate, observations_only
from noetloom.learning_worker import check_native_identity, native, parity, score
from noetloom.storage import (RunLease, RunWriter, StorageError, default_cache, file_digest,
                              source_identity, storage_snapshot, tree_bytes, validate_cache)
import rust as rust_tools
from learning_setup import environment

PROTOCOL = ROOT / "experiments/EXP-0002/protocol.json"
RESERVATION = 16 * 1024**2


def identity() -> dict:
    scripts = [{"path": str(path.relative_to(ROOT)), "sha256": file_digest(path)}
               for path in sorted((ROOT / "scripts").glob("*.py"))]
    return {"python": source_identity(ROOT), "rust": rust_tools.rust_source(), "scripts": scripts,
            "protocol_sha256": file_digest(PROTOCOL),
            "design_sha256": file_digest(ROOT / "experiments/EXP-0002/design.md")}


def artifacts(directory: Path) -> list[dict]:
    tree_bytes(directory)  # Refuse symlinks and special files, including nested state.
    return [{"path": str(path.relative_to(directory)), "sha256": file_digest(path), "bytes": path.stat().st_size}
            for path in sorted(directory.rglob("*")) if path.is_file() and path != directory / "manifest.json"]


def check_manifest(directory: Path, *, current: bool = True) -> dict:
    manifest = read_json(directory / "manifest.json", 1024**2)
    if manifest.get("status") != "passed" or manifest.get("schema_version") != "noetloom.learning_run.v1":
        raise ContractError("learning run is incomplete or unsupported")
    if artifacts(directory) != manifest["artifacts"]:
        raise ContractError("learning artifact inventory, bytes, or hashes changed")
    if current and manifest["source"] != identity():
        raise ContractError("learning evidence source differs; preserve the original code for replay")
    return manifest


def supervised(command: list[str], env: dict, directory: Path, policy: dict, seconds: int,
               rss_limit: int, output_limit: int) -> dict:
    start = time.monotonic()
    observed_peak = 0
    with (directory / "worker.log").open("xb") as handle:
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        try:
            while child.poll() is None:
                if time.monotonic() - start > seconds:
                    raise StorageError("learning worker exceeded the registered wall-clock budget")
                if tree_bytes(directory) > output_limit:
                    raise StorageError("learning output exceeds its reservation")
                storage_snapshot(directory.parent, policy)
                snapshot = subprocess.run(["ps", "-axo", "pid=,pgid=,rss="], capture_output=True,
                                          text=True, check=True, timeout=5)
                rss = sum(int(row[2]) * 1024 for line in snapshot.stdout.splitlines()
                          if len(row := line.split()) == 3 and int(row[1]) == child.pid)
                observed_peak = max(observed_peak, rss)
                if observed_peak > rss_limit:
                    raise StorageError("learning process group exceeded sampled peak-RSS admission")
                time.sleep(0.1)
            if child.returncode:
                tail = (directory / "worker.log").read_text(errors="replace")[-1600:]
                raise StorageError(f"learning worker exited {child.returncode}: {tail}")
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
    return {"elapsed_seconds": time.monotonic() - start, "sampled_process_group_peak_rss_bytes": observed_peak,
            "memory_scope": "Sampled process-group RSS; final worker OS high-water RSS also checked; no OS memory sandbox."}


def _new_writer(cache: Path, prefix: str, seconds: int = 120) -> RunWriter:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    return RunWriter(cache / (prefix + "-" + stamp), RESERVATION, seconds)


def _finish(writer: RunWriter, source: dict, binary: Path, binary_hash: str, policy: dict,
            details: dict) -> dict:
    writer.checkpoint()
    if source != identity() or file_digest(binary) != binary_hash:
        raise ContractError("source or native executable changed during learning work")
    manifest = {"schema_version": "noetloom.learning_run.v1", "status": "passed",
                "source": source, "binary_sha256": binary_hash, "resource_policy": policy,
                "git_head_context": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True, timeout=10).stdout.strip(),
                "artifacts": artifacts(writer.directory), **details}
    reserve = len(canonical_bytes(manifest)) + 65536
    if tree_bytes(writer.directory) + reserve > writer.max_bytes:
        raise StorageError("learning completion marker exceeds output admission")
    storage_snapshot(writer.directory.parent, policy, reserve)
    writer.write_json("manifest.json", manifest)
    return {"status": "passed", "directory": str(writer.directory), "manifest_sha256": file_digest(writer.directory / "manifest.json")}


def execute(kind: str, admission: Path | None = None, arm: str | None = None, seed: int | None = None) -> dict:
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT)
    validate_learning_protocol(protocol, policy)
    cache = validate_cache(default_cache(), ROOT)
    tooling, env = environment()
    env.update(PYTHONPATH=os.pathsep.join((str(tooling / "learning-python"), str(ROOT))),
               PYTHONNOUSERSITE="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    binary = tooling / "cargo-target/release/examples/learning"
    with RunLease(cache, policy, RESERVATION):
        compile_seconds = 0.0
        if kind == "preflight":
            _, rust_env = rust_tools.tooling_environment()
            rust_tools.check_tooling(tooling, policy["min_free_disk_bytes"], reserve=True)
            compile_started = time.monotonic()
            rust_tools.cargo(["build", "--release", "--example", "learning", "--locked"], rust_env, tooling, policy)
            compile_seconds = time.monotonic() - compile_started
        else:
            if admission is None or arm not in protocol["arms"] or seed not in protocol["seeds"]:
                raise ContractError("run needs an admitted preflight, registered arm and seed")
            admitted = check_manifest(admission)
            if admitted.get("kind") != "preflight":
                raise ContractError("admission is not a completed preflight")
            if admitted["binary_sha256"] != file_digest(binary):
                raise ContractError("native binary differs from preflight")
            if read_json(admission / "protocol.json") != protocol or read_json(admission / "data.json", 8 * 1024**2) != generate(protocol):
                raise ContractError("admitted data or protocol differs from frozen generation")
            # Include incomplete attempts: a failed seed cannot be silently retried.
            for request_path in cache.glob("learning-train-*/request.json"):
                request = read_json(request_path)
                if request.get("admission") == str(admission) and request.get("arm") == arm and request.get("seed") == seed:
                    raise ContractError("this admitted arm/seed already has an attempt; record a protocol decision before retrying")
        source, binary_hash = identity(), file_digest(binary)
        seconds = protocol["preflight"]["max_wall_seconds"] if kind == "preflight" else protocol["budget"]["max_wall_seconds_per_run"]
        output_limit = protocol["preflight"]["max_output_bytes"] if kind == "preflight" else protocol["budget"]["max_output_bytes_per_run"]
        writer = _new_writer(cache, "learning-" + kind, seconds)
        writer.max_bytes = output_limit
        try:
            writer.write_json("protocol.json", protocol)
            writer.write_json("request.json", {"kind": kind, "binary": str(binary), "rust_source": source["rust"],
                              "admission": str(admission) if admission else None, "arm": arm, "seed": seed,
                              "admission_manifest_sha256": file_digest(admission / "manifest.json") if admission else None})
            monitor = supervised([sys.executable, "-B", "-m", "noetloom.learning_worker", kind, str(writer.directory)],
                                 env, writer.directory, policy, seconds, protocol["budget"]["max_peak_rss_bytes"], output_limit)
            report = read_json(writer.directory / ("preflight.json" if kind == "preflight" else "report.json"))
            if report["peak_rss_bytes"] > protocol["budget"]["max_peak_rss_bytes"]:
                raise StorageError("worker's final OS peak RSS exceeds admission")
            return _finish(writer, source, binary, binary_hash, policy,
                           {"kind": kind, "monitor": monitor, "compile_seconds": compile_seconds, "admission": str(admission) if admission else None,
                            "arm": arm, "seed": seed})
        except Exception as error:
            try:
                writer.write_json("failure.json", {"status": "failed", "error": str(error)})
            except (OSError, StorageError):
                pass
            raise


def verify(directory: Path) -> dict:
    original = check_manifest(directory)
    if original["kind"] != "train":
        raise ContractError("verify expects a completed training run")
    request = read_json(directory / "request.json")
    admission = Path(request["admission"])
    check_manifest(admission)
    if file_digest(admission / "manifest.json") != request["admission_manifest_sha256"]:
        raise ContractError("preflight manifest differs from the run's admitted identity")
    data = read_json(admission / "data.json", 8 * 1024**2)["datasets"]
    protocol = read_json(directory / "protocol.json")
    validate_learning_protocol(protocol, load_policy(ROOT))
    if protocol != read_json(PROTOCOL) or read_json(admission / "data.json", 8 * 1024**2) != generate(protocol):
        raise ContractError("replay data or protocol differs from registered generator")
    rows = [row for family in protocol["data"]["test_families"] for row in data[f"test_{family}"]]
    # JSON root here is deliberately an array; the general object loader is not appropriate.
    if json.loads((directory / "observations.json").read_bytes()) != observations_only(rows):
        raise ContractError("runtime observations differ from frozen data")
    parameters = read_json(directory / "selected.json")
    original_report = read_json(directory / "report.json")
    for key in ("arm", "seed"):
        if not (parameters[key] == original_report[key] == request[key] == original[key]):
            raise ContractError("run arm/seed identities disagree")
    if parameters["step"] != original_report["selected_step"]:
        raise ContractError("selected checkpoint step identity differs")
    binary = Path(request["binary"])
    if file_digest(binary) != original["binary_sha256"]:
        raise ContractError("verification binary differs from original")
    policy = load_policy(ROOT)
    cache = validate_cache(default_cache(), ROOT)
    with RunLease(cache, policy, RESERVATION):
        writer = _new_writer(cache, "learning-verify")
        try:
            source = identity()
            # Copy only bounded, hash-verified parameters and observations into a fresh run.
            for name in ("selected.json", "observations.json"):
                with (writer.directory / name).open("xb") as handle:
                    handle.write((directory / name).read_bytes())
            receipt = native(binary, writer.directory, "selected.json", "observations.json", "replayed.json")
            check_native_identity(receipt, writer.directory / "selected.json", writer.directory / "observations.json", source["rust"])
            tensor = read_json(directory / "tensor-parity.json", 8 * 1024**2)
            maximum = parity(receipt, rows, tensor)
            actual = score(receipt, rows)
            expected = original_report["scored"]
            # Wall observations cannot be reproduced; deterministic operation counters must match.
            actual["native_metrics"].pop("elapsed_ns")
            expected["native_metrics"].pop("elapsed_ns")
            if actual != expected:
                raise ContractError("replayed predictions, scores, or deterministic operation counts differ")
            writer.write_json("verification.json", {"status": "passed", "run": str(directory),
                              "manifest_sha256": file_digest(directory / "manifest.json"),
                              "queries_replayed": len(rows) * 8, "maximum_logit_error": maximum,
                              "proof_scope": "Source-bound checkpoint inference and scoring replay; does not independently retrain or attest historical timing."})
            return _finish(writer, source, binary, original["binary_sha256"], policy, {"kind": "verification", "run": str(directory)})
        except Exception as error:
            writer.write_json("failure.json", {"status": "failed", "error": str(error)})
            raise


def summarize(admission: Path) -> dict:
    check_manifest(admission)
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT)
    cache = validate_cache(default_cache(), ROOT)
    reports = {}
    identities = []
    for path in cache.glob("learning-train-*/request.json"):
        request = read_json(path)
        if request.get("admission") != str(admission):
            continue
        manifest = check_manifest(path.parent)
        report = read_json(path.parent / "report.json")
        key = (report["arm"], report["seed"])
        if key in reports:
            raise ContractError("duplicate training attempt in summary")
        reports[key] = report
        identities.append({"arm": key[0], "seed": key[1], "directory": str(path.parent),
                           "manifest_sha256": file_digest(path.parent / "manifest.json")})
    if set(reports) != {(arm, seed) for arm in protocol["arms"] for seed in protocol["seeds"]}:
        raise ContractError("incomplete campaign; no comparative research decision is admitted")
    def paired(other: str) -> dict:
        values = [reports["selective", seed]["scored"]["accuracy"] - reports[other, seed]["scored"]["accuracy"] for seed in protocol["seeds"]]
        mean = statistics.mean(values)
        half = 2.7764451052 * statistics.stdev(values) / math.sqrt(5)
        return {"differences_by_seed": values, "mean": mean, "low": mean - half, "high": mean + half}
    arm_results = {}
    for arm in protocol["arms"]:
        values = [reports[arm, seed] for seed in protocol["seeds"]]
        arm_results[arm] = {"accuracy": statistics.mean(r["scored"]["accuracy"] for r in values),
            "families": {family: statistics.mean(r["scored"]["families"][f"test_{family}"]["accuracy"] for r in values) for family in protocol["data"]["test_families"]},
            "seeds": [{"seed": r["seed"], "accuracy": r["scored"]["accuracy"], "families": r["scored"]["families"],
                       "selected_step": r["selected_step"], "elapsed_seconds": r["elapsed_seconds"],
                       "native_evaluation_seconds": r["native_evaluation_seconds"],
                       "native_process_seconds": r["native_process_seconds"],
                       "native_metrics": r["scored"]["native_metrics"], "peak_rss_bytes": r["peak_rss_bytes"]} for r in values]}
    comparisons = {other: paired(other) for other in ("dense", "frozen_routing", "no_history")}
    ratio = sum(reports["selective", seed]["scored"]["native_metrics"]["payload_read_bytes"] for seed in protocol["seeds"]) / sum(reports["dense", seed]["scored"]["native_metrics"]["payload_read_bytes"] for seed in protocol["seeds"])
    acceptance, candidate = protocol["acceptance"], arm_results["selective"]
    gates = {"base": candidate["families"]["base"] >= acceptance["base_accuracy"],
             "mean": candidate["accuracy"] >= acceptance["all_family_accuracy"],
             "worst_family": min(candidate["families"].values()) >= acceptance["minimum_family_accuracy"],
             "dense_noninferiority": comparisons["dense"]["low"] >= acceptance["dense_difference_ci_low"],
             "routing_ablation": comparisons["frozen_routing"]["low"] > acceptance["ablation_difference_ci_low"],
             "memory_ablation": comparisons["no_history"]["low"] > acceptance["ablation_difference_ci_low"],
             "payload_read_ratio": ratio <= acceptance["max_payload_read_ratio"]}
    with RunLease(cache, policy, RESERVATION):
        writer = _new_writer(cache, "learning-summary")
        summary = {"status": "completed", "decision": "retain" if all(gates.values()) else "reject_registered_configuration",
                   "gates": gates, "arms": arm_results, "paired_seed_intervals": comparisons,
                   "payload_read_ratio": ratio, "training_runs": sorted(identities, key=lambda r: (r["arm"], r["seed"])),
                   "scope": protocol["claim_boundary"], "speed_claim": False}
        writer.write_json("summary.json", summary)
        binary = Path(read_json(admission / "request.json")["binary"])
        result = _finish(writer, identity(), binary, file_digest(binary), policy, {"kind": "summary", "admission": str(admission)})
        result["decision"] = summary["decision"]
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "run", "campaign", "verify", "summarize"))
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--arm")
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            result = execute("preflight")
        elif args.command == "run":
            result = execute("train", args.admission.resolve() if args.admission else None, args.arm, args.seed)
        elif args.command == "campaign":
            if args.admission is None: raise ContractError("campaign needs --admission")
            admission = args.admission.resolve()
            protocol = read_json(PROTOCOL)
            for seed in protocol["seeds"]:
                for arm in protocol["arms"]:
                    result = execute("train", admission, arm, seed)
                    print(json.dumps({**result, "arm": arm, "seed": seed}), flush=True)
                    checked = verify(Path(result["directory"]))
                    print(json.dumps({**checked, "action": "verification"}), flush=True)
            result = summarize(admission)
        elif args.command == "verify":
            if args.run is None: raise ContractError("verify needs --run")
            result = verify(args.run.resolve())
        else:
            if args.admission is None: raise ContractError("summarize needs --admission")
            result = summarize(args.admission.resolve())
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ContractError, OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
