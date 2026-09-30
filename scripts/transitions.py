#!/usr/bin/env python3
"""Admit, fit and replay EXP-0006 under a persistent serialized attempt ledger."""
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
from noetloom.calibration_records import write
from noetloom.contracts import ContractError, load_policy, read_json
from noetloom.storage import RunLease, RunWriter, StorageError, default_cache, file_digest, storage_snapshot, tree_bytes, validate_cache
from noetloom.transition_contracts import validate_protocol
import learning as supervisor
from learning_setup import environment

PROTOCOL = ROOT / "experiments/EXP-0006/protocol.json"


def identity() -> dict:
    paths = sorted([*(ROOT / "noetloom").glob("*.py"), *(ROOT / "scripts").glob("*.py"), PROTOCOL,
                    ROOT / "experiments/EXP-0006/design.md", ROOT / "config/resource-policy-calibration.json"])
    return {"files": [{"path": str(path.relative_to(ROOT)), "sha256": file_digest(path)} for path in paths]}


def committed(source: dict) -> str:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    for row in source["files"]:
        result = subprocess.run(["git", "show", f"{head}:{row['path']}"], cwd=ROOT, capture_output=True, timeout=10)
        if result.returncode or hashlib.sha256(result.stdout).hexdigest() != row["sha256"]:
            raise ContractError("commit reviewed transition sources and registration before execution")
    return head


def recovery_ready() -> dict:
    prior = read_json(ROOT / "docs/evidence/N-007-2026-09-30.json")["retention"]
    archive = Path(prior["destination"]).expanduser() / "evidence.tar.gz"
    if not prior["all_restored_files_verified"] or file_digest(archive) != prior["archive_sha256"]:
        raise ContractError("existing learned evidence private backup is missing or changed")
    return {"archive_sha256": prior["archive_sha256"], "protection": "Owner-selected private same-disk copy; not an independent failure domain."}


def records(cache: Path) -> list[tuple[Path, dict]]:
    rows = [(path.parent, read_json(path)) for path in sorted(cache.glob("transitions-*/request.json"))]
    if any(row.get("experiment") != "EXP-0006" for _, row in rows):
        raise ContractError("unknown transition ledger entry")
    return rows


def attempt_key(request: dict) -> tuple:
    if request["kind"] in {"development", "injection"}:
        return tuple(request.get(key) for key in ("kind", "stage", "arm", "condition", "seed"))
    if request["kind"] == "replay":
        return "replay", str(Path(request["original"]).resolve()), bool(request.get("development_transfer"))
    return (request["kind"],)


def validate_request(request: dict, protocol: dict) -> None:
    kind = request["kind"]
    if kind in {"development", "injection"}:
        if request.get("original") is not None or request.get("development_transfer"):
            raise ContractError("fitting does not accept replay arguments")
        if request["arm"] not in protocol["arms"] or request["stage"] not in protocol["stages"] or request["condition"] not in {c["name"] for c in protocol["conditions"]}:
            raise ContractError("unregistered transition fit identity")
        if kind == "injection" and attempt_key(request) != ("injection", "tiny", "shared_transition", "lr003", 9919):
            raise ContractError("unregistered transition failure injection")
    elif kind in {"preflight", "replay"}:
        if any(request.get(key) is not None for key in ("stage", "arm", "condition", "seed")):
            raise ContractError("non-fitting operation does not accept fit arguments")
        if kind == "preflight" and (request.get("original") is not None or request.get("development_transfer")):
            raise ContractError("preflight does not accept replay arguments")
        if kind == "replay" and not request.get("original"):
            raise ContractError("replay needs its original run")
    else:
        raise ContractError("unregistered transition operation")


def manifest(directory: Path, *, passed: bool = True) -> dict:
    result = read_json(directory / "manifest.json", 2 * 1024**2)
    if result.get("schema_version") != "noetloom.transitions_run.v1" or (passed and result["status"] != "passed"):
        raise ContractError("transition attempt is incomplete or failed")
    if result["artifacts"] != supervisor.artifacts(directory) or result["source"] != identity():
        raise ContractError("transition artifacts or executable source differ")
    return result


def stage_selection(cache: Path, protocol: dict, arm: str, stage: str) -> str | None:
    current = identity()
    rows = [(path, row) for path, row in records(cache) if row["kind"] == "development" and row["arm"] == arm and row["stage"] == stage]
    if len({attempt_key(row) for _, row in rows}) != len(rows):
        raise ContractError("duplicate scientific fits in transition ledger")
    attempts = {(row["condition"], row["seed"]): path for path, row in rows if row["source"] == current}
    for condition in protocol["conditions"]:
        admitted = []
        for seed in protocol["development_seeds"]:
            path = attempts.get((condition["name"], seed))
            if path is None or not (path / "manifest.json").is_file():
                admitted.append(False)
            else:
                result = manifest(path, passed=False)
                admitted.append(result["status"] == "passed" and read_json(path / "fit.json")["acquisition"]["passed"])
        if all(admitted):
            return condition["name"]
    return None


def require_transfer(cache: Path, protocol: dict, original: Path) -> None:
    old = read_json(original / "request.json")
    if (old["kind"] != "development" or old["stage"] != "mixed"
            or stage_selection(cache, protocol, old["arm"], "mixed") != old["condition"]):
        raise ContractError("development transfer requires complete three-seed mixed acquisition")


def admit(cache: Path, protocol: dict, request: dict) -> None:
    previous, kind = records(cache), request["kind"]
    validate_request(request, protocol)
    limits = {"development": "max_development_attempts", "preflight": "max_preflight_attempts",
              "injection": "max_failure_injections", "replay": "max_replays"}
    if kind not in limits or sum(row["kind"] == kind for _, row in previous) >= protocol["budget"][limits[kind]]:
        raise ContractError("transition attempt ceiling reached or unregistered execution kind")
    if kind != "preflight" and any(attempt_key(row) == attempt_key(request) for _, row in previous):
        raise ContractError("transition identity already attempted; failures remain charged")
    reserve = {"updates": 48 if kind == "preflight" else 8 if kind == "injection" else 0 if kind == "replay"
               else protocol["training"]["steps"].get(request["stage"], 2048),
               "presentations": 50000, "prefix_predictions": 180000, "seconds": 120,
               "bytes": protocol["budget"]["max_output_bytes_per_run"]}
    charged = {key: 0 for key in reserve}
    for path, old in previous:
        value = read_json(path / "manifest.json") if (path / "manifest.json").is_file() else {}
        usage = value.get("usage", {})
        for key in reserve:
            charged[key] += tree_bytes(path) if key == "bytes" else usage.get(key, 2048 if key == "updates" else reserve[key])
    for key, ceiling in (("updates", "max_updates_total"), ("presentations", "max_presentations_total"),
                         ("prefix_predictions", "max_prefix_predictions_total"), ("seconds", "max_wall_seconds_total"),
                         ("bytes", "max_artifact_bytes_total")):
        if charged[key] + reserve[key] > protocol["budget"][ceiling]:
            raise ContractError("transition total search budget exhausted: " + key)
    if kind == "development":
        if request["arm"] not in protocol["arms"] or request["seed"] not in protocol["development_seeds"] or request["stage"] not in protocol["stages"]:
            raise ContractError("unregistered transition development identity")
        stage = protocol["stages"].index(request["stage"])
        if stage and stage_selection(cache, protocol, request["arm"], protocol["stages"][stage - 1]) is None:
            raise ContractError("preceding transition stage lacks all-seed acquisition")
        first = [path for path, row in previous if row["kind"] == kind and row["arm"] == request["arm"]
                 and row["stage"] == request["stage"] and row["condition"] == "lr003" and row["source"] == request["source"]]
        if request["condition"] == "lr010" and (len(first) != 3 or any(not (path / "manifest.json").is_file() for path in first)
                                                or stage_selection(cache, protocol, request["arm"], request["stage"]) is not None):
            raise ContractError("second learning rate requires a completed unsuccessful first condition")


def execute(kind: str, *, admission: Path | None = None, arm: str | None = None, stage: str | None = None,
            condition: str | None = None, seed: int | None = None, original: Path | None = None,
            development_transfer: bool = False) -> dict:
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT, "local-calibration")
    validate_protocol(protocol, policy)
    original = original.resolve() if original is not None else None
    source, cache = identity(), validate_cache(default_cache(), ROOT)
    head = committed(source)
    request = {"experiment": "EXP-0006", "kind": kind, "arm": arm, "stage": stage, "condition": condition,
               "seed": seed, "created_unix": time.time(), "source_commit": head, "source": source,
               "protocol_sha256": file_digest(PROTOCOL), "original": str(original) if original else None,
               "development_transfer": development_transfer}
    validate_request(request, protocol)
    if kind in {"development", "injection"}:
        if admission is None or manifest(admission)["kind"] != "preflight":
            raise ContractError("transition fitting requires this source's successful preflight")
        if condition not in {row["name"] for row in protocol["conditions"]}:
            raise ContractError("unregistered transition learning condition")
        request.update(admission=str(admission), admission_sha256=file_digest(admission / "manifest.json"), recovery=recovery_ready())
    if kind == "replay":
        if original is None:
            raise ContractError("replay requires a completed development fit or transfer evaluation")
        original_kind = manifest(original)["kind"]
        if original_kind == "replay":
            old = read_json(original / "request.json")
            if not old["development_transfer"] or development_transfer:
                raise ContractError("only a transfer-bearing evaluation permits nested replay")
            parent = original.parent / Path(old["original"]).name
            if manifest(parent)["kind"] != "development" or file_digest(parent / "manifest.json") != old["original_manifest_sha256"]:
                raise ContractError("transfer evaluation parent differs")
        elif original_kind != "development":
            raise ContractError("replay requires a completed development fit or transfer evaluation")
        request["original_manifest_sha256"] = file_digest(original / "manifest.json")
        if development_transfer:
            require_transfer(cache, protocol, original)
    elif development_transfer:
        raise ContractError("development transfer must be a separately admitted replay")
    tooling, env = environment()
    env.update(PYTHONPATH=os.pathsep.join((str(tooling / "learning-python"), str(ROOT))),
               PYTHONNOUSERSITE="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    budget = protocol["budget"]
    with RunLease(cache, policy, budget["max_output_bytes_per_run"]):
        admit(cache, protocol, request)
        writer = RunWriter(cache / ("transitions-" + kind + "-" + uuid.uuid4().hex[:10]), budget["max_output_bytes_per_run"], 120)
        directory = writer.directory
        writer.write_json("protocol.json", protocol)
        writer.write_json("request.json", request)
        fit_kind = kind in {"development", "injection"}
        for name, status in (("fitting", "not_started" if fit_kind else "not_applicable"),
                             ("verification", "not_started" if fit_kind else "running"), ("resource", "admitted")):
            write(directory, name + "-status.json", {"status": status})
        start, error, monitor = time.monotonic(), None, None
        try:
            monitor = supervisor.supervised([sys.executable, "-B", "-m", "noetloom.transition_worker", str(directory)], env,
                                           directory, policy, 120, budget["max_peak_rss_bytes"], writer.max_bytes)
        except Exception as caught:
            error = str(caught)
        elapsed, resource_error = time.monotonic() - start, None
        measured = read_json(directory / "work.json") if (directory / "work.json").is_file() else {
            "updates": 2048 if fit_kind else 48 if kind == "preflight" else 0,
            "presentations": 50000, "prefix_predictions": 180000, "scope": "missing completion evidence charged at ceiling"}
        measured["seconds"] = elapsed
        try:
            resources = read_json(directory / "worker-resources.json")
            if (elapsed > 120 or resources["peak_rss_bytes"] > budget["max_peak_rss_bytes"]
                    or source != identity() or tree_bytes(directory) + 65536 > writer.max_bytes
                    or measured["presentations"] > 50000 or measured["prefix_predictions"] > 180000):
                raise StorageError("final transition time, memory, source, presentations or output admission exceeded")
            storage_snapshot(cache, policy, 65536)
            write(directory, "resource-status.json", {"status": "completed", "elapsed_seconds": elapsed,
                  "scope": "Sampled process-group and final high-water RSS; no OS memory sandbox."})
        except Exception as caught:
            resource_error = str(caught)
            write(directory, "resource-status.json", {"status": "failed_or_unknown", "error": resource_error})
        fitting, verification = read_json(directory / "fitting-status.json"), read_json(directory / "verification-status.json")
        if error and fitting["status"] in {"not_started", "running"}:
            write(directory, "fitting-status.json", {"status": "interrupted", "error": error})
        if not fit_kind or (error and verification["status"] in {"not_started", "running"}):
            write(directory, "verification-status.json", {"status": "failed" if error else "completed", "error": error})
        result = {"schema_version": "noetloom.transitions_run.v1", "status": "failed" if error or resource_error else "passed",
                  "kind": kind, "source": source, "source_commit": head, "usage": measured, "monitor": monitor,
                  "error": error, "resource_error": resource_error,
                  "outcomes": {name: read_json(directory / (name + "-status.json")) for name in ("fitting", "verification", "resource")}}
        result["artifacts"] = supervisor.artifacts(directory)
        write(directory, "manifest.json", result)
        return {"directory": str(directory), "status": result["status"], "outcomes": result["outcomes"],
                "manifest_sha256": file_digest(directory / "manifest.json")}


def summary() -> dict:
    cache, protocol = validate_cache(default_cache(), ROOT), read_json(PROTOCOL)
    rows = []
    for directory, request in records(cache):
        value = read_json(directory / "manifest.json") if (directory / "manifest.json").is_file() else {}
        fit = read_json(directory / "fit.json") if (directory / "fit.json").is_file() else None
        rows.append({"run": directory.name, **{key: request[key] for key in ("kind", "arm", "stage", "condition", "seed")},
                     "status": value.get("status", "incomplete"), "usage": value.get("usage"),
                     "acquisition": fit["acquisition"] if fit else None,
                     "selected": fit["measurements"][fit["selected_measurement"]] if fit else None})
    return {"attempts": rows, "selections": {arm: {stage: stage_selection(cache, protocol, arm, stage)
            for stage in protocol["stages"]} for arm in protocol["arms"]}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "train", "inject", "verify", "summary"))
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--arm", choices=("shared_transition", "direct"))
    parser.add_argument("--stage", choices=("tiny", "one", "mixed"))
    parser.add_argument("--condition", choices=("lr003", "lr010"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--development-transfer", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "summary":
            result = summary()
        elif args.command == "inject":
            result = execute("injection", admission=args.admission, arm="shared_transition", stage="tiny", condition="lr003", seed=9919)
            if tuple(result["outcomes"][name]["status"] for name in ("fitting", "verification", "resource")) != ("completed", "failed", "completed"):
                raise ContractError("injected post-fit failure did not preserve the expected outcomes")
            result["expected_failure_verified"] = True
        else:
            result = execute({"preflight": "preflight", "train": "development", "verify": "replay"}[args.command],
                             admission=args.admission, arm=args.arm, stage=args.stage, condition=args.condition,
                             seed=args.seed, original=args.run, development_transfer=args.development_transfer)
        print(json.dumps(result, indent=2))
        return int(result.get("status") == "failed" and not result.get("expected_failure_verified"))
    except (ContractError, OSError, subprocess.SubprocessError, StopIteration) as error:
        print(json.dumps({"status": "refused_or_failed", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
