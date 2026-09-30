#!/usr/bin/env python3
"""Bounded post-hoc development diagnostics; never changes EXP-0006's registration."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noetloom.calibration_records import write
from noetloom.contracts import ContractError, load_policy, read_json
from noetloom.storage import RunLease, RunWriter, default_cache, file_digest, storage_snapshot, tree_bytes, validate_cache
from noetloom.transition_diagnostics import validate_registration
import learning as supervisor
from learning_setup import environment
from transitions import committed

PROTOCOL = ROOT / "experiments/EXP-0007/diagnostics.json"


def identity() -> dict:
    protocol = read_json(PROTOCOL)
    paths = sorted([*(ROOT / "noetloom").glob("*.py"), *(ROOT / "scripts").glob("*.py"), PROTOCOL,
                    ROOT / "experiments/EXP-0007/design.md", ROOT / "config/resource-policy-calibration.json",
                    ROOT / protocol["historical_evidence"], ROOT / protocol["historical_protocol"]])
    return {"files": [{"path": str(path.relative_to(ROOT)), "sha256": file_digest(path)} for path in paths]}


def check_historical_binding(protocol: dict) -> dict:
    path = ROOT / protocol["historical_evidence"]
    if file_digest(path) != protocol["historical_evidence_sha256"]:
        raise ContractError("diagnostic historical evidence changed")
    evidence = read_json(path)
    dependencies = {"noetloom/transition_data.py", "noetloom/transition_model.py", "noetloom/transition_torch.py",
                    "noetloom/transition_worker.py", "noetloom/transition_contracts.py", "noetloom/input_audit.py"}
    for row in evidence["source"]["files"]:
        if row["path"] in dependencies and file_digest(ROOT / row["path"]) != row["sha256"]:
            raise ContractError("diagnostic generator or original predictor code changed")
    backup = evidence["backup"]
    if file_digest(Path(backup["destination"]).expanduser() / "evidence.tar.gz") != backup["archive_sha256"]:
        raise ContractError("retained prior private archive is missing or changed")
    return {"archive_sha256": backup["archive_sha256"], "scope": "Owner-selected private same-disk copy; prior restore evidence retained."}


def admit(cache: Path, protocol: dict, kind: str) -> None:
    if kind not in {"run", "replay"}:
        raise ContractError("unregistered diagnostic operation")
    requests = [(path.parent, read_json(path)) for path in sorted(cache.glob("transition-diagnostic-*/request.json"))]
    limits = protocol["budget"]
    if (len(requests) >= limits["max_attempts"]
            or sum(r["kind"] == kind for _, r in requests) >= limits["max_runs" if kind == "run" else "max_replays"]):
        raise ContractError("diagnostic attempt ceiling reached; failed attempts remain charged")
    seconds = 0.0
    for directory, _ in requests:
        result = read_json(directory / "manifest.json") if (directory / "manifest.json").is_file() else {}
        seconds += result.get("seconds", limits["max_wall_seconds_per_run"])
    if (seconds + limits["max_wall_seconds_per_run"] > limits["max_wall_seconds_total"]
            or sum(tree_bytes(d) for d, _ in requests) + limits["max_output_bytes_per_run"] > limits["max_artifact_bytes_total"]):
        raise ContractError("diagnostic total budget exhausted")


def validated_run(directory: Path) -> dict:
    manifest = read_json(directory / "manifest.json")
    if (manifest.get("schema_version") != "noetloom.transition_diagnostic_run.v1" or manifest["status"] != "passed"
            or manifest["source"] != identity() or manifest["artifacts"] != supervisor.artifacts(directory)):
        raise ContractError("diagnostic replay requires complete matching source and artifact bytes")
    return manifest


def execute(kind: str, *, original: Path | None = None, input_root: Path | None = None) -> dict:
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT, "local-calibration")
    validate_registration(protocol)
    if (kind not in {"run", "replay"} or (kind == "run" and original is not None)
            or (kind == "replay" and (original is None or input_root is not None))):
        raise ContractError("diagnostic run/replay arguments differ")
    source, cache = identity(), validate_cache(default_cache(), ROOT)
    head, recovery = committed(source), check_historical_binding(protocol)
    original = original.resolve() if original is not None else None
    if original:
        validated_run(original)
    request = {"experiment": protocol["id"], "kind": kind, "source_commit": head, "source": source,
               "source_root": str(ROOT), "created_unix": time.time(), "protocol_sha256": file_digest(PROTOCOL),
               "input_root": str((input_root or cache).resolve()), "original": str(original) if original else None,
               "original_manifest_sha256": file_digest(original / "manifest.json") if original else None,
               "prior_recovery": recovery}
    tooling, env = environment()
    env.update(PYTHONPATH=os.pathsep.join((str(tooling / "learning-python"), str(ROOT))),
               PYTHONNOUSERSITE="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    limits = protocol["budget"]
    with RunLease(cache, policy, limits["max_output_bytes_per_run"]):
        admit(cache, protocol, kind)
        writer = RunWriter(cache / ("transition-diagnostic-" + kind + "-" + uuid.uuid4().hex[:10]),
                           limits["max_output_bytes_per_run"], limits["max_wall_seconds_per_run"])
        directory = writer.directory
        writer.write_json("protocol.json", protocol)
        writer.write_json("request.json", request)
        write(directory, "fitting-status.json", {"status": "not_started"})
        write(directory, "verification-status.json", {"status": "not_started"})
        write(directory, "resource-status.json", {"status": "admitted"})
        start, error, monitor = time.monotonic(), None, None
        try:
            monitor = supervisor.supervised([sys.executable, "-B", "-m", "noetloom.transition_diagnostics", str(directory)],
                                           env, directory, policy, limits["max_wall_seconds_per_run"],
                                           limits["max_peak_rss_bytes"], writer.max_bytes)
        except Exception as caught:
            error = str(caught)
        seconds, resource_error = time.monotonic() - start, None
        try:
            if identity() != source:
                raise ContractError("diagnostic source changed during execution")
            resources = read_json(directory / "worker-resources.json")
            if (resources["peak_rss_bytes"] > limits["max_peak_rss_bytes"]
                    or seconds > limits["max_wall_seconds_per_run"]
                    or tree_bytes(directory) + 65536 > writer.max_bytes):
                raise ContractError("diagnostic final memory, time or output admission exceeded")
            storage_snapshot(cache, policy, 65536)
            write(directory, "resource-status.json", {"status": "completed", "seconds": seconds,
                  "scope": "Sampled process-group and worker high-water RSS; no OS memory sandbox."})
        except Exception as caught:
            resource_error = str(caught)
            write(directory, "resource-status.json", {"status": "failed_or_unknown", "error": resource_error})
        for name in ("fitting", "verification"):
            status = read_json(directory / (name + "-status.json"))["status"]
            if status in {"not_started", "running"}:
                error = error or "diagnostic worker omitted a completion boundary"
                write(directory, name + "-status.json", {"status": "interrupted", "error": error})
        usage = read_json(directory / "work.json") if (directory / "work.json").is_file() else {
            "scope": "Incomplete usage; attempt charged at registered ceilings.",
            "affine_fit_examples": limits["max_affine_fit_examples_per_run"],
            "scored_trajectories": limits["max_scored_trajectories_per_run"],
            "forward_prefixes": limits["max_forward_prefixes_per_run"]}
        result = {"schema_version": "noetloom.transition_diagnostic_run.v1", "status": "failed" if error or resource_error else "passed",
                  "kind": kind, "source": source, "source_commit": head, "seconds": seconds, "usage": usage,
                  "monitor": monitor, "error": error, "resource_error": resource_error,
                  "outcomes": {key: read_json(directory / (key + "-status.json")) for key in ("fitting", "verification", "resource")}}
        result["artifacts"] = supervisor.artifacts(directory)
        write(directory, "manifest.json", result)
        return {"directory": str(directory), "status": result["status"], "seconds": seconds,
                "manifest_sha256": file_digest(directory / "manifest.json"), "outcomes": result["outcomes"]}


def main() -> int:
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "verify"))
    parser.add_argument("--original", type=Path)
    parser.add_argument("--input-root", type=Path)
    args = parser.parse_args()
    try:
        result = execute("run" if args.command == "run" else "replay", original=args.original, input_root=args.input_root)
        print(json.dumps(result, indent=2))
        return int(result["status"] != "passed")
    except (ContractError, OSError, KeyError) as error:
        print(json.dumps({"status": "refused_or_failed", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
