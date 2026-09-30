"""Admitted harness execution and independent artifact/replay verification."""

from __future__ import annotations

import datetime as dt
import hashlib
import platform
import math
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from .contracts import (ContractError, canonical_bytes, fields, integer, load_policy, read_json,
                        text, validate_experiment, validate_policy, version)
from .recall import evaluate
from .storage import (RunLease, RunWriter, StorageError, file_digest, source_identity,
                      storage_snapshot, validate_cache)

ARTIFACT_NAMES = {"protocol.json", "resource-policy.json", "source.json", "report.json", "predictions.jsonl"}
RUNTIME_ROOT = Path(__file__).resolve().parent.parent
LOADED_SOURCE = source_identity(RUNTIME_ROOT)


def runtime_source(repo_root: Path) -> dict[str, Any]:
    if not repo_root.samefile(RUNTIME_ROOT):
        raise ContractError("repository must match the imported runtime root; run a fresh process from that checkout")
    current = source_identity(RUNTIME_ROOT)
    if current != LOADED_SOURCE:
        raise ContractError("runtime source changed after import; restart from the intended checkout")
    return current


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def git_state(root: Path) -> dict[str, Any]:
    try:
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
                              capture_output=True, timeout=5, check=False)
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                               capture_output=True, timeout=5, check=True)
        return {"head": head.stdout.decode().strip() if head.returncode == 0 else None,
                "dirty": bool(dirty.stdout)}
    except (OSError, subprocess.SubprocessError):
        return {"head": None, "dirty": None}


def peak_rss_bytes() -> int | None:
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(peak if sys.platform == "darwin" else peak * 1024)
    except (ImportError, AttributeError, OSError):
        return None


def run_experiment(repo_root: Path, protocol_path: Path, cache_root: Path, *,
                   profile: str = "local-small") -> dict[str, Any]:
    source = runtime_source(repo_root)
    policy = load_policy(repo_root, profile)
    protocol = read_json(protocol_path)
    validate_experiment(protocol, policy)
    root = validate_cache(cache_root, repo_root)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:10]
    directory = root / run_id
    budget = protocol["budget"]
    started_at = utc_now()
    with RunLease(root, policy, budget["max_output_bytes"]):
        writer = RunWriter(directory, budget["max_output_bytes"], budget["max_wall_seconds"])
        try:
            writer.write_json("source.json", source)
            writer.write_json("protocol.json", protocol)
            writer.write_json("resource-policy.json", policy)
            last_storage_check = time.monotonic()

            def checkpoint() -> None:
                nonlocal last_storage_check
                writer.checkpoint()
                now = time.monotonic()
                if now - last_storage_check >= 1:
                    remaining = max(0, budget["max_output_bytes"] - writer.bytes_written)
                    storage_snapshot(root, policy, remaining)
                    last_storage_check = now

            with (directory / "predictions.jsonl").open("xb") as handle:
                result = evaluate(protocol, lambda row: writer.append(handle, canonical_bytes(row)), checkpoint)
            report = {
                "schema_version": "noetloom.harness_report.v1",
                "experiment_id": protocol["id"],
                "evaluation": result,
                "claim_boundary": protocol["claim_boundary"],
                "measurements": {
                    "wall_seconds_before_report": time.monotonic() - writer.started,
                    "process_peak_rss_bytes": peak_rss_bytes(),
                    "rss_scope": "whole_process_high_water_mark_including_harness",
                    "memory_limit_enforced": False,
                    "wall_limit_enforcement": "cooperative_checkpoints",
                },
                "environment": {"python": platform.python_version(), "system": platform.system(),
                                "machine": platform.machine()},
            }
            writer.write_json("report.json", report)
            artifacts = [{"path": name, "bytes": (directory / name).stat().st_size,
                          "sha256": file_digest(directory / name)} for name in sorted(ARTIFACT_NAMES)]
            manifest = {
                "schema_version": "noetloom.run.v1", "run_id": run_id,
                "experiment_id": protocol["id"], "started_at": started_at,
                "source_digest": source["digest"], "git": git_state(repo_root),
                "result": result["verdict"], "artifacts": artifacts,
            }
            storage_snapshot(root, policy, len(canonical_bytes(manifest)))
            writer.write_json("manifest.json", manifest)
            return {"status": result["verdict"], "run_id": run_id, "directory": str(directory),
                    "bytes_written": writer.bytes_written, "predictions": result["predictions"],
                    "learning_demonstrated": False}
        except BaseException:
            # Partial evidence remains owned by this run; a missing manifest is never success.
            # No automatic deletion, fallback execution, or invented completion record.
            raise


def _manifest(directory: Path, policy: dict[str, Any]) -> dict[str, Any]:
    if directory.is_symlink() or not directory.is_dir():
        raise ContractError("run must be an ordinary directory")
    contents = {path.name for path in directory.iterdir()}
    if contents != ARTIFACT_NAMES | {"manifest.json"}:
        raise ContractError("run has missing or unexpected artifacts; partial runs cannot verify")
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ContractError("run artifacts must be ordinary files")
    manifest = read_json(directory / "manifest.json")
    fields(manifest, {"schema_version", "run_id", "experiment_id", "started_at", "source_digest",
                      "git", "result", "artifacts"}, "run manifest")
    version(manifest, "noetloom.run.v1")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,79}", text(manifest["run_id"], "run_id")):
        raise ContractError("invalid run id")
    if manifest["run_id"] != directory.name:
        raise ContractError("run directory name must match its manifest identity")
    if text(manifest["result"], "manifest result") not in {"passed", "failed"}:
        raise ContractError("invalid manifest result")
    try:
        started = dt.datetime.fromisoformat(text(manifest["started_at"], "started_at"))
    except ValueError as exc:
        raise ContractError("invalid run start timestamp") from exc
    if started.tzinfo is None:
        raise ContractError("run start timestamp requires a timezone")
    if not re.fullmatch(r"[0-9a-f]{64}", text(manifest["source_digest"], "source_digest")):
        raise ContractError("invalid source digest")
    git = manifest["git"]
    fields(git, {"head", "dirty"}, "git provenance")
    if git["head"] is not None and not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", text(git["head"], "git head")):
        raise ContractError("invalid Git commit identity")
    if git["dirty"] is not None and type(git["dirty"]) is not bool:
        raise ContractError("git dirty must be boolean or null")
    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) != len(ARTIFACT_NAMES):
        raise ContractError("invalid artifact inventory")
    seen: set[str] = set()
    total = (directory / "manifest.json").stat().st_size
    for entry in artifacts:
        fields(entry, {"path", "bytes", "sha256"}, "artifact")
        name = text(entry["path"], "artifact path")
        if name not in ARTIFACT_NAMES or name in seen:
            raise ContractError("artifact paths must be unique members of the run format")
        seen.add(name)
        integer(entry["bytes"], "artifact bytes", 1, policy["max_run_output_bytes"])
        if not re.fullmatch(r"[0-9a-f]{64}", text(entry["sha256"], "artifact digest")):
            raise ContractError("invalid artifact digest")
        total += entry["bytes"]
        if total > policy["max_run_output_bytes"]:
            raise ContractError("run artifacts exceed current verification budget")
        path = directory / name
        if path.stat().st_size != entry["bytes"] or file_digest(path) != entry["sha256"]:
            raise ContractError(f"artifact identity mismatch: {name}")
    return manifest


def _measurements(report: dict[str, Any], protocol: dict[str, Any]) -> None:
    measurements = report["measurements"]
    fields(measurements, {"wall_seconds_before_report", "process_peak_rss_bytes", "rss_scope",
                          "memory_limit_enforced", "wall_limit_enforcement"}, "measurements")
    seconds = measurements["wall_seconds_before_report"]
    if (type(seconds) not in (int, float) or not math.isfinite(seconds)
            or not 0 <= seconds <= protocol["budget"]["max_wall_seconds"]):
        raise ContractError("invalid recorded wall time")
    if measurements["process_peak_rss_bytes"] is not None:
        integer(measurements["process_peak_rss_bytes"], "recorded peak RSS", 0)
    if (measurements["rss_scope"] != "whole_process_high_water_mark_including_harness"
            or measurements["memory_limit_enforced"] is not False
            or measurements["wall_limit_enforcement"] != "cooperative_checkpoints"):
        raise ContractError("incorrect resource-measurement scope")
    fields(report["environment"], {"python", "system", "machine"}, "environment")
    for key, value in report["environment"].items():
        text(value, f"environment {key}")


def verify_run(repo_root: Path, directory: Path, *, profile: str = "local-small") -> dict[str, Any]:
    """Verify bytes, then regenerate predictions and scores with matching runtime source."""
    current_source = runtime_source(repo_root)
    policy = load_policy(repo_root, profile)
    manifest = _manifest(directory, policy)
    recorded_policy = read_json(directory / "resource-policy.json")
    validate_policy(recorded_policy)
    protocol = read_json(directory / "protocol.json")
    validate_experiment(protocol, policy)  # A stored policy cannot expand this host's admission.
    validate_experiment(protocol, recorded_policy)
    total = sum(path.stat().st_size for path in directory.iterdir())
    if total > protocol["budget"]["max_output_bytes"]:
        raise ContractError("run exceeds its own protocol output budget")
    source = read_json(directory / "source.json")
    if source != current_source or source.get("digest") != manifest["source_digest"]:
        raise ContractError("runtime source differs from run; check out its source before replay")
    if manifest["experiment_id"] != protocol["id"]:
        raise ContractError("manifest experiment id differs from protocol")
    report = read_json(directory / "report.json")
    fields(report, {"schema_version", "experiment_id", "evaluation", "claim_boundary", "measurements",
                    "environment"}, "harness report")
    version(report, "noetloom.harness_report.v1")
    if report["experiment_id"] != protocol["id"] or report["claim_boundary"] != protocol["claim_boundary"]:
        raise ContractError("report does not identify the recorded protocol and claim boundary")
    _measurements(report, protocol)
    digest = hashlib.sha256()
    started = time.monotonic()

    def checkpoint() -> None:
        if time.monotonic() - started > protocol["budget"]["max_wall_seconds"]:
            raise StorageError("replay wall-clock budget exceeded")

    expected = evaluate(protocol, lambda row: digest.update(canonical_bytes(row)), checkpoint)
    if digest.hexdigest() != file_digest(directory / "predictions.jsonl"):
        raise ContractError("prediction stream does not match deterministic replay")
    if canonical_bytes(expected) != canonical_bytes(report["evaluation"]) or expected["verdict"] != manifest["result"]:
        raise ContractError("reported scores or verdict do not match replay")
    return {
        "status": "verified", "harness_verdict": expected["verdict"],
        "run_id": manifest["run_id"], "experiment_id": protocol["id"],
        "manifest_sha256": file_digest(directory / "manifest.json"),
        "source_digest": source["digest"], "predictions_replayed": expected["predictions"],
        "evidence_scope": "artifact integrity and deterministic harness replay; no learned capability",
    }
