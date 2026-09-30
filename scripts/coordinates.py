#!/usr/bin/env python3
"""Admit and replay the frozen EXP-0008 coordinate acquisition comparison."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noetloom.calibration_records import write
from noetloom.contracts import ContractError, load_policy, read_json
from noetloom.coordinates_contracts import validate_protocol
from noetloom.storage import RunLease, RunWriter, default_cache, file_digest, storage_snapshot, tree_bytes, validate_cache
import learning as supervisor
from learning_setup import environment
from transitions import committed

PROTOCOL = ROOT / "experiments/EXP-0008/protocol.json"
KINDS = {"preflight": "max_preflight_attempts", "injection": "max_failure_injections", "fit": "max_fit_attempts",
         "oracle": "max_oracle_attempts", "replay": "max_replay_attempts"}
USAGE_LIMITS = {"updates": ("max_updates_per_run", "max_gradient_updates_total"),
                "presentations": ("max_presentations_per_run", "max_presentations_total"),
                "forward_prefixes": ("max_forward_prefixes_per_run", "max_forward_prefixes_total")}


def identity():
    protocol = read_json(PROTOCOL)
    paths = sorted([*(ROOT / "noetloom").glob("*.py"), *(ROOT / "scripts").glob("*.py"), PROTOCOL,
                    ROOT / protocol["design"], ROOT / protocol["prior_evidence"], ROOT / "config/resource-policy-calibration.json"])
    return {"files": [{"path": str(path.relative_to(ROOT)), "sha256": file_digest(path)} for path in paths]}


def records(cache):
    result = [(path.parent, read_json(path)) for path in sorted(cache.glob("coordinates-*/request.json"))]
    if any(row.get("experiment") != "EXP-0008" or row.get("kind") not in KINDS for _, row in result):
        raise ContractError("unknown coordinate ledger entry")
    return result


def validate_request(request, protocol):
    kind = request.get("kind")
    if kind not in KINDS:
        raise ContractError("unregistered coordinate operation")
    if kind == "fit":
        if (request.get("stage") not in protocol["training"]["steps"] or request.get("arm") not in protocol["arms"]
                or type(request.get("seed")) is not int or request["seed"] not in protocol["development_seeds"]
                or request.get("condition") not in {c["name"] for c in protocol["conditions"]}
                or request.get("recovery") or bool(request.get("original")) != (request["stage"] == "mixed")):
            raise ContractError("unregistered coordinate fit identity or parent")
    elif any(request.get(key) is not None for key in ("stage", "arm", "condition", "seed")):
        raise ContractError("non-fitting operation received fit arguments")
    if kind == "replay":
        if not request.get("original"):
            raise ContractError("coordinate replay needs its original run")
    elif kind != "fit" and (request.get("original") or request.get("recovery")):
        raise ContractError("operation received replay arguments")


def key(request):
    if request["kind"] == "fit":
        return tuple(request[k] for k in ("kind", "stage", "arm", "condition", "seed"))
    if request["kind"] == "replay":
        return "replay", Path(request["original"]).name, bool(request.get("recovery"))
    return (request["kind"],)


def manifest(directory, *, passed=True):
    result = read_json(directory / "manifest.json", 2 * 1024**2)
    if (result.get("schema_version") != "noetloom.coordinates_run.v1" or (passed and result.get("status") != "passed")
            or result.get("source") != identity() or result.get("artifacts") != supervisor.artifacts(directory)):
        raise ContractError("coordinate source, artifacts or successful completion differ")
    return result


def selection(cache, protocol, arm, stage="one"):
    attempts = {(row["condition"], row["seed"]): path for path, row in records(cache)
                if row["kind"] == "fit" and row["arm"] == arm and row["stage"] == stage and row["source"] == identity()}
    if stage == "one" and any((condition["name"], seed) not in attempts
            or not (attempts[(condition["name"], seed)] / "manifest.json").is_file()
            for condition in protocol["conditions"] for seed in protocol["development_seeds"]):
        return None
    for condition in protocol["conditions"]:
        passed = []
        for seed in protocol["development_seeds"]:
            path = attempts.get((condition["name"], seed))
            ready = path is not None and (path / "manifest.json").is_file() and (path / "fit.json").is_file()
            passed.append(ready and manifest(path, passed=False)["status"] == "passed"
                          and read_json(path / "fit.json")["acquisition"]["passed"] is True)
        if all(passed):
            return condition["name"]
    return None


def require_mixed(cache, protocol, request):
    original = Path(request["original"])
    old = read_json(original / "request.json")
    if (old["kind"] != "fit" or old["stage"] != "one"
            or any(old[k] != request[k] for k in ("arm", "seed", "condition"))
            or selection(cache, protocol, request["arm"]) != request["condition"]):
        raise ContractError("mixed fitting needs every one-step seed at the selected common condition")
    for seed in protocol["development_seeds"]:
        parents = [path for path, row in records(cache) if row["kind"] == "fit" and row["stage"] == "one"
                   and row["arm"] == request["arm"] and row["condition"] == request["condition"] and row["seed"] == seed
                   and row["source"] == identity()]
        replays = [path for path, row in records(cache) if row["kind"] == "replay" and row["source"] == identity()
                   and any(Path(row["original"]).name == parent.name for parent in parents)]
        if not any((path / "manifest.json").is_file() and manifest(path, passed=False)["status"] == "passed" for path in replays):
            raise ContractError("mixed fitting needs every one-step parent fully replayed")


def reservation(protocol, request):
    budget, kind = protocol["budget"], request["kind"]
    updates = 48 if kind == "preflight" else 8 if kind == "injection" else 0
    row = request
    if kind == "replay":
        row = read_json(Path(request["original"]) / "request.json")
    if row["kind"] == "fit":
        probes = len(protocol["diagnostics"]["prediction_perturbation"]["steps"][row["stage"]])
        groups = len(protocol["diagnostics"]["prediction_perturbation"]["groups"][row["arm"]])
        updates = probes * groups + (protocol["training"]["steps"][row["stage"]] if kind == "fit" else 0)
    return {"updates": updates, "presentations": budget["max_presentations_per_run"],
            "forward_prefixes": budget["max_forward_prefixes_per_run"], "seconds": budget["max_wall_seconds_per_run"],
            "bytes": budget["max_output_bytes_per_run"]}


def admit(cache, protocol, request):
    validate_request(request, protocol)
    previous, budget = records(cache), protocol["budget"]
    if (len(previous) >= budget["max_attempts"]
            or sum(row["kind"] == request["kind"] for _, row in previous) >= budget[KINDS[request["kind"]]]):
        raise ContractError("coordinate attempt ceiling reached; failed attempts remain charged")
    if request["kind"] != "preflight" and any(key(old) == key(request) for _, old in previous):
        raise ContractError("coordinate identity already attempted; failed attempts remain charged")
    reserve, charged = reservation(protocol, request), {}
    for directory, old in previous:
        result = read_json(directory / "manifest.json") if (directory / "manifest.json").is_file() else {}
        usage, fallback = result.get("usage", {}), reservation(protocol, old)
        for name in reserve:
            value = tree_bytes(directory) if name == "bytes" else usage.get(name, fallback[name])
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ContractError("invalid coordinate resource ledger")
            charged[name] = charged.get(name, 0) + value
    ceilings = {name: limits[1] for name, limits in USAGE_LIMITS.items()}
    ceilings.update(seconds="max_wall_seconds_total", bytes="max_artifact_bytes_total")
    if any(charged.get(name, 0) + reserve[name] > budget[limit] for name, limit in ceilings.items()):
        raise ContractError("coordinate aggregate resource budget exhausted")
    if request["kind"] == "fit" and request["stage"] == "mixed":
        require_mixed(cache, protocol, request)


def recovery_ready(protocol):
    backups = read_json(ROOT / protocol["prior_evidence"])["recovery"]
    result = {}
    for view in ("aligned", "nonlinear"):
        backup = backups[view]
        archive = Path(backup["destination"]).expanduser() / "evidence.tar.gz"
        if not backup["all_restored_bytes_verified"] or file_digest(archive) != backup["archive_sha256"]:
            raise ContractError("prior private evidence copy is missing or changed")
        result[view] = backup["archive_sha256"]
    return {"archive_sha256": result, "scope": "Previously authorized private same-disk duplicate and restored-source replays."}


def execute(kind, *, stage=None, arm=None, condition=None, seed=None, admission=None, original=None, recovery=False):
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT, "local-calibration")
    validate_protocol(protocol, policy)
    source, cache = identity(), validate_cache(default_cache(), ROOT)
    head = committed(source)
    original = original.resolve() if original is not None else None
    request = {"experiment": "EXP-0008", "kind": kind, "stage": stage, "arm": arm, "condition": condition, "seed": seed,
               "source": source, "source_commit": head, "protocol_sha256": file_digest(PROTOCOL), "created_unix": time.time(),
               "original": str(original) if original else None, "recovery": recovery}
    validate_request(request, protocol)
    if kind in {"fit", "oracle", "injection"}:
        if admission is None or manifest(admission)["kind"] != "preflight":
            raise ContractError("coordinate work requires this source's completed preflight")
        request.update(admission=str(admission.resolve()), admission_sha256=file_digest(admission / "manifest.json"),
                       prior_recovery=recovery_ready(protocol))
    elif admission is not None:
        raise ContractError("operation does not accept an admission argument")
    if original:
        old_kind = manifest(original)["kind"]
        if old_kind not in ({"fit"} if kind == "fit" else {"fit", "oracle"}):
            raise ContractError("coordinate operation cannot use this original run kind")
        request["original_manifest_sha256"] = file_digest(original / "manifest.json")
    tooling, env = environment()
    env.update(PYTHONPATH=os.pathsep.join((str(tooling / "learning-python"), str(ROOT))), PYTHONNOUSERSITE="1",
               OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    budget = protocol["budget"]
    with RunLease(cache, policy, budget["max_output_bytes_per_run"]):
        admit(cache, protocol, request)
        writer = RunWriter(cache / ("coordinates-" + kind + "-" + uuid.uuid4().hex[:10]),
                           budget["max_output_bytes_per_run"], budget["max_wall_seconds_per_run"])
        directory = writer.directory
        writer.write_json("protocol.json", protocol)
        writer.write_json("request.json", request)
        for name, status in (("fitting", "not_started" if kind in {"fit", "injection"} else "not_applicable"),
                             ("verification", "not_started"), ("resource", "admitted")):
            write(directory, name + "-status.json", {"status": status})
        start, error, monitor = time.monotonic(), None, None
        try:
            monitor = supervisor.supervised([sys.executable, "-B", "-m", "noetloom.coordinates_worker", str(directory)], env,
                                           directory, policy, budget["max_wall_seconds_per_run"], budget["max_peak_rss_bytes"], writer.max_bytes)
        except Exception as caught:
            error = str(caught)
        seconds, resource_error = time.monotonic() - start, None
        usage = read_json(directory / "work.json") if (directory / "work.json").is_file() else {
            **reservation(protocol, request), "scope": "Missing usage charged at registered ceilings."}
        usage["seconds"] = seconds
        try:
            resources = read_json(directory / "worker-resources.json")
            if (source != identity() or seconds > budget["max_wall_seconds_per_run"]
                    or resources["peak_rss_bytes"] > budget["max_peak_rss_bytes"] or tree_bytes(directory) + 65536 > writer.max_bytes
                    or any(usage[key] > budget[limits[0]] for key, limits in USAGE_LIMITS.items())
                    or usage.get("auxiliary_observations", 0) > budget["max_auxiliary_observations_per_run"]):
                raise ContractError("coordinate final source, time, memory, work or output check failed")
            storage_snapshot(cache, policy, 65536)
            write(directory, "resource-status.json", {"status": "completed", "seconds": seconds,
                  "scope": "Sampled process group and worker high-water RSS; not an OS memory sandbox."})
        except Exception as caught:
            resource_error = str(caught)
            write(directory, "resource-status.json", {"status": "failed_or_unknown", "error": resource_error})
        for name in ("fitting", "verification"):
            status = read_json(directory / (name + "-status.json"))["status"]
            if status in {"not_started", "running"}:
                error = error or "worker omitted completion evidence"
                write(directory, name + "-status.json", {"status": "interrupted", "error": error})
        result = {"schema_version": "noetloom.coordinates_run.v1", "status": "failed" if error or resource_error else "passed",
                  "kind": kind, "source": source, "source_commit": head, "usage": usage, "monitor": monitor,
                  "error": error, "resource_error": resource_error,
                  "outcomes": {name: read_json(directory / (name + "-status.json")) for name in ("fitting", "verification", "resource")}}
        result["artifacts"] = supervisor.artifacts(directory)
        write(directory, "manifest.json", result)
        return {"directory": str(directory), "status": result["status"], "seconds": seconds,
                "manifest_sha256": file_digest(directory / "manifest.json"), "outcomes": result["outcomes"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "train", "oracle", "inject", "verify"))
    parser.add_argument("--stage", choices=("tiny", "one", "mixed"))
    parser.add_argument("--arm", choices=("latent", "reversible", "direct"))
    parser.add_argument("--condition", choices=("lr003", "lr010"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--original", type=Path)
    parser.add_argument("--recovery", action="store_true")
    args = parser.parse_args()
    try:
        value = execute({"train": "fit", "inject": "injection", "verify": "replay"}.get(args.command, args.command),
                        **{k: getattr(args, k) for k in ("stage", "arm", "condition", "seed", "admission", "original", "recovery")})
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0 if value["status"] == "passed" else 1
    except (ContractError, OSError) as error:
        print(json.dumps({"status": "refused", "reason": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
