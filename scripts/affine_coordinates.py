#!/usr/bin/env python3
"""Admit and replay the frozen EXP-0009 affine-coordinate comparison."""
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
from noetloom.affine_coordinates_contracts import validate_protocol
from noetloom.calibration_records import write
from noetloom.contracts import ContractError, load_policy, read_json
from noetloom.storage import RunLease, RunWriter, default_cache, file_digest, storage_snapshot, tree_bytes, validate_cache
import learning as supervisor
from learning_setup import environment
from transitions import committed

PROTOCOL = ROOT / "experiments/EXP-0009/protocol.json"
KINDS = {"preflight": "max_preflight_attempts", "injection": "max_failure_injections",
         "fit": "max_fit_attempts", "evaluate": "max_evaluation_attempts",
         "replay": "max_replay_attempts"}
USAGE_LIMITS = {
    "updates": ("max_updates_per_run", "max_gradient_updates_total"),
    "presentations": ("max_presentations_per_run", "max_presentations_total"),
    "forward_prefixes": ("max_forward_prefixes_per_run", "max_forward_prefixes_total"),
    "affine_fit_examples": ("max_affine_fit_examples_per_run", "max_affine_fit_examples_total"),
    "linear_systems": ("max_linear_systems_per_run", "max_linear_systems_total"),
}


def identity():
    protocol = read_json(PROTOCOL)
    paths = sorted([*(ROOT / "noetloom").glob("*.py"), *(ROOT / "scripts").glob("*.py"), PROTOCOL,
                    ROOT / protocol["design"], ROOT / protocol["prior_evidence"],
                    ROOT / "config/resource-policy-calibration.json"])
    return {"files": [{"path": str(path.relative_to(ROOT)), "sha256": file_digest(path)} for path in paths]}


def records(cache):
    result = [(path.parent, read_json(path)) for path in sorted(cache.glob("affine-coordinates-*/request.json"))]
    if any(row.get("experiment") != "EXP-0009" or row.get("kind") not in KINDS for _, row in result):
        raise ContractError("unknown affine-coordinate ledger entry")
    return result


def validate_request(request, protocol):
    kind = request.get("kind")
    if kind not in KINDS:
        raise ContractError("unregistered affine-coordinate operation")
    if kind == "fit":
        if (request.get("stage") not in protocol["training"]["steps"]
                or request.get("arm") not in protocol["arms"]
                or type(request.get("seed")) is not int
                or request["seed"] not in protocol["development_seeds"]
                or request.get("condition") not in {c["name"] for c in protocol["conditions"]}
                or request.get("recovery")
                or bool(request.get("original")) != (request["stage"] == "mixed")):
            raise ContractError("unregistered affine-coordinate fit identity or parent")
    elif any(request.get(key) is not None for key in ("stage", "arm", "condition", "seed")):
        raise ContractError("non-fitting operation received fit arguments")

    needs_original = kind in {"evaluate", "replay"} or (kind == "fit" and request.get("stage") == "mixed")
    if needs_original:
        if not request.get("original"):
            raise ContractError("affine-coordinate operation needs its original run")
    elif request.get("original"):
        raise ContractError("operation received an unexpected original run")
    if kind != "replay" and request.get("recovery"):
        raise ContractError("only replay accepts the recovery flag")


def key(request):
    if request["kind"] == "fit":
        return tuple(request[k] for k in ("kind", "stage", "arm", "condition", "seed"))
    if request["kind"] in {"evaluate", "replay"}:
        result = (request["kind"], Path(request["original"]).name)
        return result + ((bool(request.get("recovery")),) if request["kind"] == "replay" else ())
    return (request["kind"],)


def manifest(directory, *, passed=True):
    result = read_json(directory / "manifest.json", 2 * 1024**2)
    if (result.get("schema_version") != "noetloom.affine_coordinates_run.v1"
            or (passed and result.get("status") != "passed")
            or result.get("source") != identity()
            or result.get("artifacts") != supervisor.artifacts(directory)):
        raise ContractError("affine-coordinate source, artifacts or successful completion differ")
    return result


def _fit_for(cache, protocol, arm, stage, condition, seed):
    found = [path for path, row in records(cache)
             if row["kind"] == "fit" and row["stage"] == stage and row["arm"] == arm
             and row["condition"] == condition and row["seed"] == seed
             and row.get("source") == identity()]
    if len(found) > 1:
        raise ContractError("duplicate affine-coordinate fit identity")
    return found[0] if found else None


def _fit_passed(path):
    if path is None or not (path / "manifest.json").is_file() or not (path / "fit.json").is_file():
        return False
    return (manifest(path, passed=False)["status"] == "passed"
            and read_json(path / "fit.json").get("acquisition", {}).get("passed") is True)


def selection(cache, protocol, arm, stage="one"):
    """Select the first rate with every seed acquired, after the full one-step grid exists."""
    conditions, seeds = protocol["conditions"], protocol["development_seeds"]
    if stage == "one" and any(_fit_for(cache, protocol, arm, stage, c["name"], seed) is None
                               or not (_fit_for(cache, protocol, arm, stage, c["name"], seed) / "manifest.json").is_file()
                               for c in conditions for seed in seeds):
        return None
    for condition in conditions:
        if all(_fit_passed(_fit_for(cache, protocol, arm, stage, condition["name"], seed))
               for seed in seeds):
            return condition["name"]
    return None


def _replayed(cache, parent, *, recovery=False):
    for path, row in records(cache):
        if (row["kind"] == "replay" and row.get("source") == identity()
                and bool(row.get("recovery")) == recovery
                and Path(row.get("original", "")).name == parent.name
                and (path / "manifest.json").is_file()
                and manifest(path, passed=False)["status"] == "passed"):
            return True
    return False


def require_mixed(cache, protocol, request):
    parent = Path(request["original"])
    old = read_json(parent / "request.json")
    chosen = selection(cache, protocol, request["arm"], "one")
    if (old.get("kind") != "fit" or old.get("stage") != "one"
            or any(old.get(k) != request[k] for k in ("arm", "seed", "condition"))
            or chosen != request["condition"]):
        raise ContractError("mixed fitting needs a selected common one-step condition and matching parent")
    registered_parent = _fit_for(cache, protocol, request["arm"], "one", chosen, request["seed"])
    if registered_parent is None or registered_parent.resolve() != parent.resolve():
        raise ContractError("mixed fitting parent is not the registered selected one-step run")
    for seed in protocol["development_seeds"]:
        path = _fit_for(cache, protocol, request["arm"], "one", chosen, seed)
        if not _fit_passed(path) or not _replayed(cache, path):
            raise ContractError("mixed fitting needs every selected one-step parent acquired and fully replayed")


def require_evaluation(cache, protocol, request):
    original = Path(request["original"])
    old = read_json(original / "request.json")
    if old.get("kind") != "fit" or old.get("stage") != "mixed":
        raise ContractError("development evaluation requires a mixed fit")
    arm, condition = old.get("arm"), old.get("condition")
    selected = selection(cache, protocol, arm, "one")
    if (selected is None or condition != selected or old.get("seed") not in protocol["development_seeds"]):
        raise ContractError("development evaluation requires the arm's selected one-step condition")
    for seed in protocol["development_seeds"]:
        path = _fit_for(cache, protocol, arm, "mixed", condition, seed)
        if not _fit_passed(path) or not _replayed(cache, path):
            raise ContractError("development evaluation needs every selected mixed parent acquired and fully replayed")
        if seed == old["seed"] and path.resolve() != original.resolve():
            raise ContractError("development evaluation original is not the registered selected mixed run")


def reservation(protocol, request):
    budget, kind = protocol["budget"], request["kind"]
    updates = 32 if kind == "preflight" else 8 if kind == "injection" else 0
    affine_examples = linear_systems = 0
    row = request
    if kind in {"replay", "evaluate"}:
        row = read_json(Path(request["original"]) / "request.json") if kind == "replay" else request
    if row.get("kind") == "fit":
        stage = row["stage"]
        updates = protocol["training"]["steps"][stage] if kind == "fit" else 0
        if row["arm"] == "refit":
            solves = protocol["training"]["steps"][stage] // protocol["solver"]["interval"] + 1
            affine_examples = solves * protocol["solver"]["training_pairs"]
            linear_systems = solves * protocol["data"]["actions"]
    elif kind == "preflight":
        affine_examples = protocol["solver"]["training_pairs"]
        linear_systems = protocol["data"]["actions"] * 4
    return {"updates": updates, "affine_fit_examples": affine_examples, "linear_systems": linear_systems,
            "presentations": budget["max_presentations_per_run"],
            "forward_prefixes": budget["max_forward_prefixes_per_run"],
            "seconds": budget["max_wall_seconds_per_run"], "bytes": budget["max_output_bytes_per_run"]}


def admit(cache, protocol, request):
    validate_request(request, protocol)
    previous, budget = records(cache), protocol["budget"]
    if (len(previous) >= budget["max_attempts"]
            or sum(row["kind"] == request["kind"] for _, row in previous) >= budget[KINDS[request["kind"]]]):
        raise ContractError("affine-coordinate attempt ceiling reached; failed attempts remain charged")
    if request["kind"] != "preflight" and any(key(old) == key(request) for _, old in previous):
        raise ContractError("affine-coordinate identity already attempted; failed attempts remain charged")
    reserve, charged = reservation(protocol, request), {}
    for directory, old in previous:
        result = read_json(directory / "manifest.json") if (directory / "manifest.json").is_file() else {}
        usage, fallback = result.get("usage", {}), reservation(protocol, old)
        for name in reserve:
            value = tree_bytes(directory) if name == "bytes" else usage.get(name, fallback[name])
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ContractError("invalid affine-coordinate resource ledger")
            charged[name] = charged.get(name, 0) + value
    ceilings = {name: limits[1] for name, limits in USAGE_LIMITS.items()}
    ceilings.update(seconds="max_wall_seconds_total", bytes="max_artifact_bytes_total")
    if any(charged.get(name, 0) + reserve[name] > budget[limit] for name, limit in ceilings.items()):
        raise ContractError("affine-coordinate aggregate resource budget exhausted")
    if request["kind"] == "fit" and request["stage"] == "mixed":
        require_mixed(cache, protocol, request)
    if request["kind"] == "evaluate":
        require_evaluation(cache, protocol, request)


def recovery_ready(protocol):
    recovery = read_json(ROOT / protocol["prior_evidence"])["recovery"]
    archive = Path(recovery["destination"]).expanduser() / "evidence.tar.gz"
    if (not recovery.get("all_restored_bytes_verified")
            or file_digest(archive) != recovery["archive_sha256"]):
        raise ContractError("prior private recovery archive is missing or changed")
    outer_inventory = Path(recovery["destination"]).expanduser() / "inventory.json"
    if (recovery.get("inventory_sha256")
            and (not outer_inventory.is_file()
                 or file_digest(outer_inventory) != recovery["inventory_sha256"])):
        raise ContractError("prior private recovery inventory is missing or changed")
    nested = recovery.get("recovery", {})
    restored = nested.get("replays", [])
    if (nested.get("all_files_verified") is not True or len(restored) != 8
            or any(row.get("status") != "passed" for row in restored)):
        raise ContractError("prior restored-source replay receipts are incomplete")
    inventory_path = Path(nested.get("directory", "")) / "inventory.json"
    inventory_sha = nested.get("inventory_sha256")
    if inventory_sha and (not inventory_path.is_file() or file_digest(inventory_path) != inventory_sha):
        raise ContractError("prior private recovery inventory is missing or changed")
    return {"archive_sha256": recovery["archive_sha256"], "inventory_sha256": inventory_sha,
            "restored_source_replays": len(restored),
            "scope": recovery.get("limitation", "Previously authorized same-disk private duplicate.")}


def execute(kind, *, stage=None, arm=None, condition=None, seed=None, admission=None,
            original=None, recovery=False):
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT, "local-calibration")
    validate_protocol(protocol, policy)
    source, cache = identity(), validate_cache(default_cache(), ROOT)
    head = committed(source)
    original = original.resolve() if original is not None else None
    request = {"experiment": "EXP-0009", "kind": kind, "stage": stage, "arm": arm,
               "condition": condition, "seed": seed, "source": source, "source_commit": head,
               "protocol_sha256": file_digest(PROTOCOL), "created_unix": time.time(),
               "original": str(original) if original else None, "recovery": recovery}
    validate_request(request, protocol)
    if kind in {"fit", "evaluate", "injection"}:
        if admission is None or manifest(admission)["kind"] != "preflight":
            raise ContractError("affine-coordinate work requires this source's completed preflight")
        request.update(admission=str(admission.resolve()), admission_sha256=file_digest(admission / "manifest.json"),
                       prior_recovery=recovery_ready(protocol))
    elif admission is not None:
        raise ContractError("operation does not accept an admission argument")
    if original:
        old = manifest(original)
        accepted = {"fit"} if kind in {"fit", "evaluate"} else {"fit", "evaluate"}
        if old["kind"] not in accepted:
            raise ContractError("affine-coordinate operation cannot use this original run kind")
        request["original_manifest_sha256"] = file_digest(original / "manifest.json")
    tooling, env = environment()
    env.update(PYTHONPATH=os.pathsep.join((str(tooling / "learning-python"), str(ROOT))),
               PYTHONNOUSERSITE="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    budget = protocol["budget"]
    with RunLease(cache, policy, budget["max_output_bytes_per_run"]):
        admit(cache, protocol, request)
        writer = RunWriter(cache / ("affine-coordinates-" + kind + "-" + uuid.uuid4().hex[:10]),
                           budget["max_output_bytes_per_run"], budget["max_wall_seconds_per_run"])
        directory = writer.directory
        writer.write_json("protocol.json", protocol)
        writer.write_json("request.json", request)
        for name, status in (("fitting", "not_started" if kind in {"fit", "injection"} else "not_applicable"),
                             ("verification", "not_started"), ("resource", "admitted")):
            write(directory, name + "-status.json", {"status": status})
        start, error, monitor = time.monotonic(), None, None
        try:
            monitor = supervisor.supervised([sys.executable, "-B", "-m", "noetloom.affine_coordinates_worker", str(directory)],
                                           env, directory, policy, budget["max_wall_seconds_per_run"],
                                           budget["max_peak_rss_bytes"], writer.max_bytes)
        except Exception as caught:
            error = str(caught)
        seconds, resource_error = time.monotonic() - start, None
        usage = read_json(directory / "work.json") if (directory / "work.json").is_file() else {
            **reservation(protocol, request), "scope": "Missing usage charged at registered ceilings."}
        usage["seconds"] = seconds
        try:
            resources = read_json(directory / "worker-resources.json")
            if (source != identity() or seconds > budget["max_wall_seconds_per_run"]
                    or resources["peak_rss_bytes"] > budget["max_peak_rss_bytes"]
                    or tree_bytes(directory) + 65536 > writer.max_bytes
                    or any(usage[key] > budget[limits[0]] for key, limits in USAGE_LIMITS.items())
                    or usage.get("auxiliary_observations", 0) > budget["max_auxiliary_observations_per_run"]):
                raise ContractError("affine-coordinate final source, time, memory, work or output check failed")
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
        result = {"schema_version": "noetloom.affine_coordinates_run.v1",
                  "status": "failed" if error or resource_error else "passed", "kind": kind,
                  "source": source, "source_commit": head, "usage": usage, "monitor": monitor,
                  "error": error, "resource_error": resource_error,
                  "outcomes": {name: read_json(directory / (name + "-status.json"))
                               for name in ("fitting", "verification", "resource")}}
        result["artifacts"] = supervisor.artifacts(directory)
        write(directory, "manifest.json", result)
        return {"directory": str(directory), "status": result["status"], "seconds": seconds,
                "manifest_sha256": file_digest(directory / "manifest.json"), "outcomes": result["outcomes"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "train", "inject", "evaluate", "verify"))
    parser.add_argument("--stage", choices=("one", "mixed"))
    parser.add_argument("--arm", choices=("joint", "refit"))
    parser.add_argument("--condition", choices=("lr003", "lr010"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--original", type=Path)
    parser.add_argument("--recovery", action="store_true")
    args = parser.parse_args()
    try:
        kind = {"train": "fit", "inject": "injection", "verify": "replay"}.get(args.command, args.command)
        value = execute(kind, **{k: getattr(args, k) for k in
                                 ("stage", "arm", "condition", "seed", "admission", "original", "recovery")})
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0 if value["status"] == "passed" else 1
    except (ContractError, OSError) as error:
        print(json.dumps({"status": "refused", "reason": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
