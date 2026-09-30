#!/usr/bin/env python3
"""Admit, fit and replay the bounded EXP-0005 development pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noetloom.calibration_contracts import validate_calibration_protocol
from noetloom.calibration_records import write
from noetloom.contracts import ContractError, canonical_bytes, load_policy, read_json
from noetloom.storage import RunLease, RunWriter, StorageError, default_cache, file_digest, storage_snapshot, tree_bytes, validate_cache
import learning as supervisor
from learning_setup import environment

PROTOCOL = ROOT / "experiments/EXP-0005/protocol.json"
CONFIRMATION = ROOT / "experiments/EXP-0005/confirmation.json"
RECOVERY = ROOT / "docs/evidence/N-007-recovery.json"


def identity() -> dict:
    paths = sorted([*(ROOT / "noetloom").glob("*.py"), *(ROOT / "scripts").glob("*.py"), PROTOCOL,
                    ROOT / "experiments/EXP-0005/design.md", ROOT / "config/resource-policy-calibration.json"])
    return {"files": [{"path": str(path.relative_to(ROOT)), "sha256": file_digest(path)} for path in paths]}


def committed(source: dict) -> str:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    for row in source["files"]:
        saved = subprocess.run(["git", "show", f"{head}:{row['path']}"], cwd=ROOT, capture_output=True, timeout=10)
        if saved.returncode or hashlib.sha256(saved.stdout).hexdigest() != row["sha256"]:
            raise ContractError("commit the reviewed protocol and executable sources before calibration execution")
    return head


def recovery_ready() -> dict:
    record = read_json(RECOVERY)
    archive = Path(record["destination"]).expanduser() / record["archive_name"]
    if (record["status"] != "verified_private_local_copy" or not record["restore"]["deterministic_rows_equal"]
            or not record["restore"]["all_inventory_files_verified"] or file_digest(archive) != record["archive_sha256"]):
        raise ContractError("owner-selected private backup/restore evidence is not available")
    return {"record_sha256": file_digest(RECOVERY), "archive_sha256": record["archive_sha256"],
            "protection": "owner-selected same-disk private copy"}


def records(cache: Path) -> list[tuple[Path, dict]]:
    result = []
    for path in sorted(cache.glob("calibration-*/request.json")):
        request = read_json(path)
        if request.get("experiment") != "EXP-0005":
            raise ContractError("unrecognized attempt in the calibration ledger")
        result.append((path.parent, request))
    return result


def manifest(directory: Path, *, passed: bool = True) -> dict:
    result = read_json(directory / "manifest.json", 2 * 1024**2)
    if result.get("schema_version") != "noetloom.calibration_run.v1" or (passed and result["status"] != "passed"):
        raise ContractError("calibration run is incomplete or failed")
    if result["artifacts"] != supervisor.artifacts(directory):
        raise ContractError("calibration inventory, bytes or hashes changed")
    if result["source"] != identity():
        raise ContractError("calibration source differs; use its preserved source revision")
    return result


def stage_selection(cache: Path, protocol: dict, arm: str, stage: str) -> str | None:
    attempts = {(q.get("condition"), q.get("seed")): p for p, q in records(cache)
                if q["kind"] == "development" and q["arm"] == arm and q["stage"] == stage}
    for condition in protocol["conditions"]:
        passed = True
        for seed in protocol["development_seeds"]:
            path = attempts.get((condition["name"], seed))
            if path is None or not (path / "manifest.json").is_file():
                passed = False
                continue
            record = manifest(path, passed=False)
            if record["status"] != "passed" or not read_json(path / "fit.json")["acquisition"]["passed"]:
                passed = False
        if passed:
            return condition["name"]
    return None


def confirmation_record(cache: Path, protocol: dict) -> dict:
    value = read_json(CONFIRMATION)
    saved = subprocess.run(["git", "show", "HEAD:experiments/EXP-0005/confirmation.json"], cwd=ROOT, capture_output=True)
    if saved.returncode or saved.stdout != CONFIRMATION.read_bytes():
        raise ContractError("confirmation settings must be committed before final data access")
    expected = {"schema_version", "seeds", "arms", "conditions", "acquisition", "transfer", "missing_runs", "claim", "development_summary_sha256"}
    if set(value) != expected or value["schema_version"] != "noetloom.calibration_confirmation.v1":
        raise ContractError("unsupported confirmation registration")
    if (not isinstance(value["seeds"], list) or len(value["seeds"]) != 5 or len(set(value["seeds"])) != 5
            or any(type(seed) is not int or seed <= 0 or seed in protocol["development_seeds"] for seed in value["seeds"])):
        raise ContractError("confirmation needs five fresh registered seeds")
    if not value["arms"] or len(set(value["arms"])) != len(value["arms"]) or set(value["conditions"]) != set(value["arms"]):
        raise ContractError("confirmation arms/conditions differ")
    for arm in value["arms"]:
        if arm not in protocol["arms"] or stage_selection(cache, protocol, arm, "mixed") != value["conditions"][arm]:
            raise ContractError("confirmation arm lacks its frozen acquisition selection")
    return value


def admit(cache: Path, protocol: dict, request: dict) -> None:
    previous = records(cache)
    kind = request["kind"]
    ceilings = {"development": "max_development_attempts", "confirmation": "max_confirmation_attempts",
                "preflight": "max_preflight_attempts", "injection": "max_failure_injections", "replay": "max_replays"}
    if kind not in ceilings or sum(q["kind"] == kind for _, q in previous) >= protocol["budget"][ceilings[kind]]:
        raise ContractError("calibration attempt ceiling reached")
    identity_keys = ("kind", "stage", "arm", "condition", "seed", "original")
    if kind != "preflight" and any(all(q.get(k) == request.get(k) for k in identity_keys) for _, q in previous):
        raise ContractError("attempt identity already exists; failed or interrupted attempts cannot be hidden")
    charged = {"updates": 0, "presentations": 0, "seconds": 0.0, "bytes": 0}
    for directory, old in previous:
        charged["bytes"] += tree_bytes(directory)
        complete = read_json(directory / "manifest.json") if (directory / "manifest.json").is_file() else {}
        usage = complete.get("usage", {})
        charged["updates"] += usage.get("updates", 2048 if old["kind"] in {"development", "confirmation"} else (72 if old["kind"] == "preflight" else 8 if old["kind"] == "injection" else 0))
        charged["presentations"] += usage.get("presentations", 50000)
        charged["seconds"] += usage.get("seconds", 120)
    reserve_updates = 72 if kind == "preflight" else 0 if kind == "replay" else 8 if kind == "injection" else next(c["steps"] for c in protocol["conditions"] if c["name"] == request["condition"])
    for key, reserve, limit in (("updates", reserve_updates, "max_updates_total"),
                                ("presentations", 50000, "max_presentations_total"),
                                ("seconds", 120, "max_wall_seconds_total"),
                                ("bytes", protocol["budget"]["max_output_bytes_per_run"], "max_artifact_bytes_total")):
        if charged[key] + reserve > protocol["budget"][limit]:
            raise ContractError("total calibration search budget exhausted: " + key)
    if kind == "development":
        if request["arm"] not in protocol["arms"] or request["seed"] not in protocol["development_seeds"] or request["stage"] not in protocol["stages"]:
            raise ContractError("unregistered development identity")
        index = protocol["stages"].index(request["stage"])
        if index and stage_selection(cache, protocol, request["arm"], protocol["stages"][index - 1]) is None:
            raise ContractError("preceding stage lacks per-seed acquisition")
        short = [q for _, q in previous if q["kind"] == kind and q["arm"] == request["arm"]
                 and q["stage"] == request["stage"] and q["condition"] == "short"]
        if request["condition"] == "long" and (len(short) != 3 or stage_selection(cache, protocol, request["arm"], request["stage"]) is not None):
            raise ContractError("long condition requires a completed unsuccessful short condition")


def usage(directory: Path, request: dict, elapsed: float) -> dict:
    if (directory / "fit.json").is_file():
        fit = read_json(directory / "fit.json")
        verification = read_json(directory / "verification-status.json")
        return {"updates": fit["completed_updates"], "presentations": fit["fitting_presentations"] + verification.get("verification_presentations", 0 if request["kind"] == "injection" else 10000),
                "seconds": elapsed, "presentation_scope": "measured forward calls; incomplete downstream verification charged at 10000"}
    if (directory / "replay.json").is_file():
        return {"updates": 0, "presentations": read_json(directory / "replay.json")["case_presentations"], "seconds": elapsed}
    if (directory / "preflight.json").is_file():
        return {"updates": 72, "presentations": 1296, "seconds": elapsed}
    return {"updates": 2048 if request["kind"] in {"development", "confirmation"} else 72 if request["kind"] == "preflight" else 8 if request["kind"] == "injection" else 0,
            "presentations": 50000, "seconds": elapsed, "presentation_scope": "conservative ceiling because completion evidence is missing"}


def execute(kind: str, *, admission: Path | None = None, arm: str | None = None, stage: str | None = None,
            condition: str | None = None, seed: int | None = None, original: Path | None = None) -> dict:
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT, "local-calibration")
    validate_calibration_protocol(protocol, policy)
    source = identity()
    head = committed(source)
    cache = validate_cache(default_cache(), ROOT)
    request = {"experiment": "EXP-0005", "kind": kind, "arm": arm, "stage": stage, "condition": condition,
               "seed": seed, "created_unix": time.time(), "source_commit": head, "source": source, "protocol_sha256": file_digest(PROTOCOL),
               "original": str(original) if original else None}
    if kind not in {"preflight", "replay"}:
        if admission is None or manifest(admission)["kind"] != "preflight":
            raise ContractError("fitting requires this source's completed preflight")
        request.update(admission=str(admission), admission_sha256=file_digest(admission / "manifest.json"), recovery=recovery_ready())
        if condition not in {c["name"] for c in protocol["conditions"]}:
            raise ContractError("unregistered training condition")
    if kind == "confirmation":
        confirmation = confirmation_record(cache, protocol)
        if arm not in confirmation["arms"] or condition != confirmation["conditions"][arm] or seed not in confirmation["seeds"] or stage != "mixed":
            raise ContractError("confirmation identity differs from its frozen settings")
        request["confirmation_sha256"] = file_digest(CONFIRMATION)
    if kind == "replay":
        if original is None or manifest(original)["kind"] not in {"development", "confirmation"}:
            raise ContractError("replay requires a complete fitted attempt")
        request["original_manifest_sha256"] = file_digest(original / "manifest.json")
    tooling, env = environment()
    env.update(PYTHONPATH=os.pathsep.join((str(tooling / "learning-python"), str(ROOT))),
               PYTHONNOUSERSITE="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    budget = protocol["budget"]
    with RunLease(cache, policy, budget["max_output_bytes_per_run"]):
        admit(cache, protocol, request)
        writer = RunWriter(cache / ("calibration-" + kind + "-" + uuid.uuid4().hex[:10]), budget["max_output_bytes_per_run"], 120)
        directory = writer.directory
        writer.write_json("protocol.json", protocol)
        writer.write_json("request.json", request)
        fit_kind = kind in {"development", "confirmation", "injection"}
        write(directory, "fitting-status.json", {"status": "not_started" if fit_kind else "not_applicable"})
        write(directory, "verification-status.json", {"status": "not_started" if fit_kind else "running"})
        write(directory, "resource-status.json", {"status": "admitted", "profile": policy["profile"]})
        error, monitor = None, None
        start = time.monotonic()
        try:
            monitor = supervisor.supervised([sys.executable, "-B", "-m", "noetloom.calibration_worker", str(directory)], env,
                directory, policy, 120, budget["max_peak_rss_bytes"], writer.max_bytes)
        except Exception as caught:
            error = str(caught)
        elapsed = time.monotonic() - start
        resource_error = None
        try:
            resources = read_json(directory / "worker-resources.json")
            if elapsed > 120 or resources["peak_rss_bytes"] > budget["max_peak_rss_bytes"]:
                raise StorageError("final time or RSS admission exceeded")
            if source != identity() or tree_bytes(directory) + 65536 > writer.max_bytes:
                raise StorageError("source changed or final artifact admission exceeded")
            storage_snapshot(cache, policy, 65536)
            write(directory, "resource-status.json", {"status": "completed", "elapsed_seconds": elapsed,
                                                     "scope": "sampled process-group RSS and final worker high-water RSS; no OS sandbox"})
        except Exception as caught:
            resource_error = str(caught)
            write(directory, "resource-status.json", {"status": "failed_or_unknown", "error": resource_error})
        fitting = read_json(directory / "fitting-status.json")
        if error and fitting["status"] in {"not_started", "running"}:
            write(directory, "fitting-status.json", {"status": "interrupted", "error": error})
        verification = read_json(directory / "verification-status.json")
        if not fit_kind or (error and verification["status"] in {"not_started", "running"}):
            write(directory, "verification-status.json", {"status": "failed" if error else "completed", "error": error})
        measured = usage(directory, request, elapsed)
        if measured["presentations"] > budget["max_case_presentations_per_run"]:
            resource_error = "actual case presentations exceeded per-run admission"
            write(directory, "resource-status.json", {"status": "failed", "error": resource_error})
        result = {"schema_version": "noetloom.calibration_run.v1", "status": "failed" if error or resource_error else "passed",
                  "kind": kind, "source": source, "source_commit": head, "usage": measured,
                  "monitor": monitor, "error": error, "resource_error": resource_error,
                  "outcomes": {name: read_json(directory / (name + "-status.json")) for name in ("fitting", "verification", "resource")}}
        result["artifacts"] = supervisor.artifacts(directory)
        write(directory, "manifest.json", result)
        return {"directory": str(directory), "status": result["status"], "kind": kind,
                "outcomes": result["outcomes"], "manifest_sha256": file_digest(directory / "manifest.json")}


def summary(cache: Path, protocol: dict) -> dict:
    attempts = []
    for directory, request in sorted(records(cache), key=lambda pair: pair[1]["created_unix"]):
        row = {"directory": str(directory), **{k: request.get(k) for k in ("kind", "arm", "stage", "condition", "seed")}}
        row["created_unix"] = request["created_unix"]
        if (directory / "manifest.json").is_file():
            run = manifest(directory, passed=False)
            row.update(status=run["status"], usage=run["usage"], outcomes=run["outcomes"], manifest_sha256=file_digest(directory / "manifest.json"))
        else:
            row["status"] = "interrupted"
        if (directory / "fit.json").is_file():
            fit = read_json(directory / "fit.json")
            row.update(acquisition=fit["acquisition"], selected=fit["measurements"][fit["selected_measurement"]])
        attempts.append(row)
    return {"schema_version": "noetloom.calibration_summary.v1", "attempts": attempts,
            "selection": {arm: {stage: stage_selection(cache, protocol, arm, stage) for stage in protocol["stages"]} for arm in protocol["arms"]}}


def pilot(admission: Path) -> dict:
    protocol, cache = read_json(PROTOCOL), validate_cache(default_cache(), ROOT)
    for stage in protocol["stages"]:
        for arm in protocol["arms"]:
            index = protocol["stages"].index(stage)
            if index and stage_selection(cache, protocol, arm, protocol["stages"][index - 1]) is None:
                continue
            for condition in protocol["conditions"]:
                if stage_selection(cache, protocol, arm, stage) is not None:
                    break
                for seed in protocol["development_seeds"]:
                    previous = next((p for p, q in records(cache) if (q["kind"], q.get("arm"), q.get("stage"), q.get("condition"), q.get("seed")) ==
                                     ("development", arm, stage, condition["name"], seed)), None)
                    if previous is None:
                        result = execute("development", admission=admission, arm=arm, stage=stage, condition=condition["name"], seed=seed)
                        print(json.dumps({"attempt": {"arm": arm, "stage": stage, "condition": condition["name"], "seed": seed}, **result}), flush=True)
                        previous = Path(result["directory"])
                    if (previous / "manifest.json").is_file() and manifest(previous, passed=False)["status"] == "passed":
                        replayed = any(q["kind"] == "replay" and q["original"] == str(previous) for _, q in records(cache))
                        if not replayed:
                            result = execute("replay", original=previous)
                            print(json.dumps(result), flush=True)
                            if result["status"] != "passed":
                                raise ContractError("replay failed; retain evidence and diagnose before continuing")
    return summary(cache, protocol)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "pilot", "train", "confirm", "verify", "inject", "summary"))
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--arm")
    parser.add_argument("--stage", choices=("tiny", "single", "mixed"))
    parser.add_argument("--condition", choices=("short", "long"))
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    try:
        if args.command == "pilot":
            result = pilot(args.admission)
        elif args.command == "summary":
            result = summary(validate_cache(default_cache(), ROOT), read_json(PROTOCOL))
        elif args.command == "verify":
            result = execute("replay", original=args.run)
        elif args.command == "inject":
            result = execute("injection", admission=args.admission, arm="shared_rows", stage="tiny", condition="short", seed=7919)
            if result["outcomes"]["fitting"]["status"] != "completed" or result["outcomes"]["verification"]["status"] != "failed" or result["outcomes"]["resource"]["status"] != "completed":
                raise ContractError("injected-failure boundary did not preserve the expected three outcomes")
            result["expected_failure_verified"] = True
        else:
            result = execute({"preflight": "preflight", "train": "development", "confirm": "confirmation"}[args.command],
                             admission=args.admission, arm=args.arm, stage=args.stage, condition=args.condition, seed=args.seed)
        print(json.dumps(result, indent=2))
        return int(result.get("status") == "failed" and not result.get("expected_failure_verified"))
    except (ContractError, OSError, subprocess.SubprocessError, StopIteration) as error:
        print(json.dumps({"status": "refused_or_failed", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
