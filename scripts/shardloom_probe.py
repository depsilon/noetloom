#!/usr/bin/env python3
"""Bounded public-engine interoperability probe; no provider adoption or performance claim."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from noetloom.contracts import ContractError, canonical_bytes, load_policy  # noqa: E402
from noetloom.storage import (RunLease, RunWriter, StorageError, default_cache, file_digest,
                              storage_snapshot, tree_bytes, validate_cache)  # noqa: E402

OUTPUT_LIMIT = 8 * 1024**2
WALL_SECONDS = 30
EVIDENCE_FIELDS = (
    "runtime_execution", "fallback_attempted", "external_engine_invoked", "upstream_vortex_scan_called",
    "public_workflow_route_attached", "public_workflow_route_status", "public_workflow_route_id",
    "public_workflow_execution_mode", "public_workflow_local_source_execution_mode",
    "public_workflow_local_source_prepared_vortex_path", "public_workflow_preparation_vortex_ingest_performed",
    "public_workflow_preparation_vortex_ingest_status", "decode_materialization_boundary",
    "local_primitive_resource_memory_budget_bytes", "local_primitive_resource_max_parallelism",
    "local_primitive_memory_admission_measurement_basis", "local_primitive_memory_fail_before_oom",
    "public_workflow_preparation_vortex_array_build_millis", "public_workflow_preparation_vortex_encode_write_millis",
    "public_workflow_preparation_vortex_final_commit_millis", "timing_surface", "route_total_timing_reported",
    "native_vortex_result_export_target_replay_statuses", "native_vortex_result_export_all_targets_committed",
    "blocker_id", "blocker_reason", "public_workflow_blocker_id", "public_workflow_blocker_reason",
)


def fixture_rows() -> list[dict]:
    operations = ("read", "apply", "write", "emit")
    return [{"episode": i // 4, "operation": operations[i % 4], "model": "scripted_fixture",
             "seed": i % 3, "scalar_ops": (i % 7) * 3 if i % 4 == 1 else 0,
             "payload_bytes": 32 if i % 4 == 0 else 0,
             "outcome": "rejected" if i % 5 == 0 else "ok"} for i in range(512)]


def queries(source: Path, rows: list[dict]) -> list[tuple[str, str, list[dict]]]:
    if "'" in str(source):
        raise StorageError("probe source paths containing SQL quotes are unsupported")
    groups = defaultdict(lambda: {"n": 0, "scalar_work": 0})
    for row in rows:
        groups[row["operation"]]["n"] += 1
        groups[row["operation"]]["scalar_work"] += row["scalar_ops"]
    return [
        ("total", f"SELECT count(*) AS n FROM '{source}'", [{"n": len(rows)}]),
        ("activated", f"SELECT count(*) AS n FROM '{source}' WHERE payload_bytes > 0",
         [{"n": sum(row["payload_bytes"] > 0 for row in rows)}]),
        ("grouped", f"SELECT operation, count(*) AS n, sum(scalar_ops) AS scalar_work FROM '{source}' GROUP BY operation",
         [{"operation": key, **value} for key, value in sorted(groups.items())]),
    ]


def invoke(binary: Path, args: list[str], directory: Path, name: str,
           deadline: float, cache: Path, policy: dict) -> tuple[int, dict, float]:
    stdout = directory / f"{name}.stdout.json"
    stderr = directory / f"{name}.stderr.txt"
    started = time.monotonic()
    with stdout.open("xb") as out, stderr.open("xb") as err:
        process = subprocess.Popen([str(binary), *args, "--format", "json"], cwd=directory,
                                   stdout=out, stderr=err, start_new_session=True)
        try:
            while True:
                try:
                    code = process.wait(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= deadline:
                        raise StorageError("ShardLoom probe exceeded its 30-second deadline")
                    used = tree_bytes(directory)
                    if used > OUTPUT_LIMIT:
                        raise StorageError("ShardLoom probe exceeded its 8 MiB output reservation")
                    storage_snapshot(cache, policy, max(0, OUTPUT_LIMIT - used))
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
    if stdout.stat().st_size > 1024**2 or stderr.stat().st_size > 1024**2:
        raise StorageError("provider diagnostic exceeds 1 MiB")
    try:
        envelope = json.loads(stdout.read_bytes())
    except (ValueError, UnicodeDecodeError):
        envelope = {"status": "invalid_output", "stderr": stderr.read_text(errors="replace")[:4096]}
    return code, envelope, time.monotonic() - started


def field_map(envelope: dict) -> dict[str, str]:
    rows = envelope.get("fields", [])
    keys = [row["key"] for row in rows]
    if len(keys) != len(set(keys)):
        raise StorageError("provider envelope has ambiguous duplicate field keys")
    return {row["key"]: row["value"] for row in rows}


def checked_rows(path: Path) -> list[dict]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 64 * 1024:
        raise StorageError("query did not produce a bounded JSONL result")
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if any(not isinstance(row, dict) or any(isinstance(value, bool) for value in row.values()) for row in rows):
        raise StorageError("query output has the wrong row or scalar types")
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))


def native_evidence(envelope: dict, fields: dict[str, str]) -> bool:
    expected = {
        "fallback_attempted": "false", "external_engine_invoked": "false", "runtime_execution": "true",
        "upstream_vortex_scan_called": "true", "public_workflow_route_attached": "true",
        "public_workflow_route_status": "admitted", "public_workflow_execution_mode": "native_vortex",
        "public_workflow_local_source_execution_mode": "prepared_vortex_then_native_vortex",
        "native_vortex_result_export_all_targets_committed": "true",
    }
    return (envelope.get("schema_version") == "shardloom.output.v2"
            and all(fields.get(key) == value for key, value in expected.items()))


def run(binary: Path, source_checkout: Path | None, cache: Path, policy: dict) -> dict:
    binary = binary.resolve(strict=True)
    if not binary.is_file():
        raise StorageError("provider binary is not a file")
    binary_sha = file_digest(binary)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("shardloom-probe-%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    writer = RunWriter(cache / run_id, OUTPUT_LIMIT, WALL_SECONDS)
    deadline = writer.started + WALL_SECONDS
    try:
        rows = fixture_rows()
        source = writer.directory / "traces.csv"
        with source.open("x", newline="") as output:
            csv_writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            csv_writer.writeheader()
            csv_writer.writerows(rows)
        context = None
        if source_checkout:
            context = {"path": str(source_checkout.resolve()), "build_binding_verified": False}
            for label, arguments in (("head", ["rev-parse", "HEAD"]), ("status", ["status", "--porcelain"])):
                result = subprocess.run(["git", "-C", str(source_checkout), *arguments], capture_output=True, timeout=5, check=True)
                context[label] = result.stdout.decode().strip()
        code, status, _ = invoke(binary, ["status"], writer.directory, "provider-status", deadline, cache, policy)
        if code or status.get("status") != "success":
            raise StorageError("provider status command failed")
        query_results = []
        for label, sql, expected in queries(source, rows):
            writer.checkpoint()
            output = writer.directory / f"{label}.rows.jsonl"
            arguments = ["run", "sql", "--input", str(source), "--input-format", "csv", "--sql", sql,
                         "--request", "write_jsonl", "--output", str(output), "--bounded", "true",
                         "--memory-gb", "1", "--max-parallelism", "2"]
            code, envelope, elapsed = invoke(binary, arguments, writer.directory, label, deadline, cache, policy)
            fields = field_map(envelope)
            result = {"name": label, "command": [str(binary), *arguments, "--format", "json"],
                      "sql": sql, "expected": expected, "exit_code": code,
                      "elapsed_seconds_including_process_and_preparation": elapsed,
                      "provider_status": envelope.get("status"), "status": "failed"}
            result["evidence"] = {key: fields[key] for key in EVIDENCE_FIELDS if key in fields}
            result["certificate_payloads"] = envelope.get("certificates", [])
            if code == 0 and envelope.get("status") == "success":
                actual = checked_rows(output)
                result["actual"] = actual
                prepared = Path(fields.get("public_workflow_local_source_prepared_vortex_path", "missing"))
                prepared_present = prepared.resolve().is_relative_to(writer.directory.resolve()) and prepared.is_file() and not prepared.is_symlink()
                result["native_evidence_complete"] = native_evidence(envelope, fields) and prepared_present
                result["rows_match"] = actual == sorted(expected, key=lambda row: json.dumps(row, sort_keys=True))
                result["status"] = "passed" if result["native_evidence_complete"] and result["rows_match"] else "mismatch_or_incomplete_evidence"
            elif any(fields.get(key) not in (None, "none", "") for key in ("blocker_id", "public_workflow_blocker_id")) or envelope.get("status") == "unsupported":
                result["status"] = "unsupported"
            query_results.append(result)
            writer.write_json(f"{label}.verification.json", result)
        if file_digest(binary) != binary_sha:
            raise StorageError("provider binary changed during the probe")
        artifacts = [{"path": path.relative_to(writer.directory).as_posix(), "bytes": path.stat().st_size,
                      "sha256": file_digest(path)} for path in sorted(writer.directory.rglob("*")) if path.is_file()]
        report = {"schema": "noetloom.shardloom_probe.v1", "status": "passed" if all(row["status"] == "passed" for row in query_results) else "partial_or_unsupported",
                  "provider_binary": str(binary), "binary_sha256": binary_sha, "source_checkout_context": context,
                  "provider_version": field_map(status).get("cli_binary_version"), "driver_sha256": file_digest(Path(__file__)),
                  "input_rows": len(rows), "input_sha256": file_digest(source), "queries": query_results,
                  "artifacts": artifacts, "training_performed": False,
                  "claim_boundary": "Synthetic evidence-analytics interoperability only. No timing comparison, cognitive-state integration, learned capability, or provider superiority."}
        reserve = len(canonical_bytes(report)) + 65_536
        if tree_bytes(writer.directory) + reserve > OUTPUT_LIMIT:
            raise StorageError("probe completion exceeds the output reservation")
        storage_snapshot(cache, policy, reserve)
        writer.write_json("report.json", report)
        return {"status": report["status"], "directory": str(writer.directory), "binary_sha256": binary_sha,
                "queries": [{"name": row["name"], "status": row["status"]} for row in query_results]}
    except Exception as error:
        try:
            writer.write_json("failure.json", {"status": "failed", "error": str(error)})
        except (OSError, StorageError):
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--source-checkout", type=Path)
    args = parser.parse_args()
    try:
        policy = load_policy(ROOT)
        cache = validate_cache(default_cache(), ROOT)
        with RunLease(cache, policy, OUTPUT_LIMIT):
            result = run(args.binary, args.source_checkout, cache, policy)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "passed" else 1
    except (ContractError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
