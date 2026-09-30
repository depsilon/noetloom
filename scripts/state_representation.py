#!/usr/bin/env python3
"""Admit the EXP-0007 development pilot, bounded fits, controls and complete replays."""
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
from noetloom.state_rep_contracts import validate_protocol
from noetloom.storage import RunLease, RunWriter, default_cache, file_digest, storage_snapshot, tree_bytes, validate_cache
import learning as supervisor
from learning_setup import environment
from transitions import committed

PROTOCOL = ROOT / "experiments/EXP-0007/protocol.json"
KINDS = {"preflight": "max_preflight_attempts", "injection": "max_failure_injections", "fit": "max_fit_attempts",
         "affine": "max_affine_attempts", "transfer": "max_transfer_attempts", "replay": "max_replay_attempts"}
USAGE_LIMITS = {"updates": ("max_updates_per_run", "max_gradient_updates_total"),
                "presentations": ("max_presentations_per_run", "max_presentations_total"),
                "forward_prefixes": ("max_forward_prefixes_per_run", "max_forward_prefixes_total"),
                "affine_fit_examples": ("max_affine_fit_examples_per_run", "max_affine_fit_examples_total")}


def identity():
    protocol = read_json(PROTOCOL)
    paths = sorted([*(ROOT / "noetloom").glob("*.py"), *(ROOT / "scripts").glob("*.py"), PROTOCOL,
                    ROOT / "experiments/EXP-0007/design.md", ROOT / protocol["prior_evidence"],
                    ROOT / "config/resource-policy-calibration.json"])
    return {"files": [{"path": str(path.relative_to(ROOT)), "sha256": file_digest(path)} for path in paths]}


def records(cache):
    result = [(path.parent, read_json(path)) for path in sorted(cache.glob("state-repr-*/request.json"))]
    if any(row.get("experiment") != "EXP-0007" or row.get("kind") not in KINDS for _, row in result):
        raise ContractError("unknown state-representation ledger entry")
    return result


def validate_request(request, protocol):
    kind = request.get("kind")
    if kind not in KINDS or request.get("observation") not in protocol["observations"]:
        raise ContractError("unregistered representation operation or observation")
    if kind in {"fit", "injection"}:
        seeds = [180797] if kind == "injection" else protocol["development_seeds"]
        if (request.get("arm") not in protocol["arms"] or type(request.get("seed")) is not int
                or request["seed"] not in seeds or request.get("condition") not in {c["name"] for c in protocol["conditions"]}
                or request.get("original") is not None or request.get("recovery")):
            raise ContractError("unregistered representation fit identity")
        if kind == "injection" and tuple(request[k] for k in ("observation", "arm", "condition", "seed")) != ("aligned", "latent", "lr003", 180797):
            raise ContractError("unregistered failure injection identity")
    elif any(request.get(key) is not None for key in ("arm", "condition", "seed")):
        raise ContractError("non-fitting operation received fit arguments")
    if kind in {"replay", "transfer"}:
        if not request.get("original") or (kind != "replay" and request.get("recovery")):
            raise ContractError("transfer or replay needs its original run")
    elif request.get("original") or request.get("recovery"):
        raise ContractError("operation received replay arguments")
    if kind == "preflight" and request["observation"] != "aligned":
        raise ContractError("one preflight audits both observation views")


def key(request):
    kind = request["kind"]
    if kind in {"fit", "injection"}:
        return tuple(request[k] for k in ("kind", "observation", "arm", "condition", "seed"))
    if kind in {"replay", "transfer"}:
        # Basename remains stable after private restore to a different root.
        return kind, Path(request["original"]).name, bool(request.get("recovery"))
    return kind, request["observation"]


def manifest(directory, *, passed=True):
    result = read_json(directory / "manifest.json", 2 * 1024**2)
    if (result.get("schema_version") != "noetloom.state_rep_run.v1" or (passed and result.get("status") != "passed")
            or result.get("source") != identity() or result.get("artifacts") != supervisor.artifacts(directory)):
        raise ContractError("representation source, artifact bytes or successful completion differ")
    return result


def selection(cache, protocol, observation, arm, *, condition=None):
    current = identity()
    attempts = {(row["condition"], row["seed"]): directory for directory, row in records(cache)
                if row["kind"] == "fit" and row["observation"] == observation and row["arm"] == arm and row["source"] == current}
    for chosen in protocol["conditions"]:
        if condition is not None and chosen["name"] != condition:
            continue
        qualified = []
        for seed in protocol["development_seeds"]:
            directory = attempts.get((chosen["name"], seed))
            if directory is None or not (directory / "manifest.json").is_file():
                qualified.append(False)
            else:
                value = manifest(directory, passed=False)
                fit = read_json(directory / "fit.json") if (directory / "fit.json").is_file() else {}
                qualified.append(value["status"] == "passed" and fit.get("acquisition_passed") is True)
        if all(qualified):
            return chosen["name"]
    return None


def require_transfer(cache, protocol, original):
    old = read_json(original / "request.json")
    if (old["kind"] != "fit" or selection(cache, protocol, old["observation"], old["arm"]) != old["condition"]):
        raise ContractError("transfer needs every arm seed to acquire at the selected common condition")
    replayed = [path for path, request in records(cache) if request["kind"] == "replay"
                and Path(request["original"]).name == original.name and request["source"] == identity()]
    if not any((path / "manifest.json").is_file() and manifest(path, passed=False)["status"] == "passed" for path in replayed):
        raise ContractError("transfer needs complete measurement and checkpoint-selection replay")


def reservation(protocol, request):
    budget, kind = protocol["budget"], request["kind"]
    refit = kind == "affine" or (kind == "replay" and read_json(Path(request["original"]) / "request.json")["kind"] == "affine")
    return {"updates": 4352 if kind == "fit" else 48 if kind == "preflight" else 8 if kind == "injection" else 0,
            "presentations": budget["max_presentations_per_run"], "forward_prefixes": budget["max_forward_prefixes_per_run"],
            "affine_fit_examples": 512 if refit else 0,
            "seconds": budget["max_wall_seconds_per_run"], "bytes": budget["max_output_bytes_per_run"]}


def admit(cache, protocol, request):
    validate_request(request, protocol)
    previous, budget = records(cache), protocol["budget"]
    if (len(previous) >= budget["max_attempts"]
            or sum(row["kind"] == request["kind"] for _, row in previous) >= budget[KINDS[request["kind"]]]):
        raise ContractError("representation attempt ceiling reached; failures remain charged")
    if request["kind"] != "preflight" and any(key(old) == key(request) for _, old in previous):
        raise ContractError("representation identity already attempted; failures remain charged")
    reserve, charged, view_bytes = reservation(protocol, request), {}, 0
    for directory, old in previous:
        result = read_json(directory / "manifest.json") if (directory / "manifest.json").is_file() else {}
        usage, fallback = result.get("usage", {}), reservation(protocol, old)
        for name in reserve:
            value = tree_bytes(directory) if name == "bytes" else usage.get(name, fallback[name])
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ContractError("invalid resource ledger usage")
            charged[name] = charged.get(name, 0) + value
        if old["observation"] == request["observation"]:
            view_bytes += tree_bytes(directory)
    for name, (_, ceiling) in USAGE_LIMITS.items():
        if charged.get(name, 0) + reserve[name] > budget[ceiling]:
            raise ContractError("representation total budget exhausted: " + name)
    for name, ceiling in (("seconds", "max_wall_seconds_total"), ("bytes", "max_artifact_bytes_total")):
        if charged.get(name, 0) + reserve[name] > budget[ceiling]:
            raise ContractError("representation total budget exhausted: " + name)
    if view_bytes + reserve["bytes"] > budget["max_artifact_bytes_per_observation"]:
        raise ContractError("representation per-observation archive budget exhausted")
    if request["kind"] == "fit" and request["observation"] == "nonlinear":
        if selection(cache, protocol, "aligned", request["arm"]) is None:
            raise ContractError("nonlinear fitting needs all three aligned seeds to acquire at a common condition")


def recovery_ready(protocol):
    backup = read_json(ROOT / protocol["prior_evidence"])["recovery"]
    archive = Path(backup["destination"]).expanduser() / "evidence.tar.gz"
    if file_digest(archive) != backup["archive_sha256"]:
        raise ContractError("prior diagnostic private copy is missing or changed")
    return {"archive_sha256": backup["archive_sha256"], "scope": "Owner-selected private same-disk copy."}


def execute(kind, *, observation=None, arm=None, condition=None, seed=None, admission=None, original=None, recovery=False):
    protocol, policy = read_json(PROTOCOL), load_policy(ROOT, "local-calibration")
    validate_protocol(protocol, policy)
    source, cache = identity(), validate_cache(default_cache(), ROOT)
    head = committed(source)
    if original is not None:
        original = original.resolve()
        old = read_json(original / "request.json")
        if observation is not None and observation != old["observation"]:
            raise ContractError("original observation differs from request")
        observation = old["observation"]
    if observation is None and kind == "preflight":
        observation = "aligned"
    request = {"experiment": "EXP-0007", "kind": kind, "observation": observation, "arm": arm,
               "condition": condition, "seed": seed, "source": source, "source_commit": head,
               "protocol_sha256": file_digest(PROTOCOL), "created_unix": time.time(),
               "original": str(original) if original else None, "recovery": recovery}
    validate_request(request, protocol)
    if kind in {"fit", "affine", "injection"}:
        if admission is None or manifest(admission)["kind"] != "preflight":
            raise ContractError("fitting requires this source's completed preflight")
        request.update(admission=str(admission.resolve()), admission_sha256=file_digest(admission / "manifest.json"),
                       prior_recovery=recovery_ready(protocol))
    elif admission is not None:
        raise ContractError("non-fitting operation does not accept an admission argument")
    if original:
        original_kind = manifest(original)["kind"]
        if (kind == "transfer" and original_kind != "fit") or (kind == "replay" and original_kind not in {"fit", "affine", "transfer"}):
            raise ContractError("operation cannot use this original run kind")
        request["original_manifest_sha256"] = file_digest(original / "manifest.json")
    tooling, env = environment()
    env.update(PYTHONPATH=os.pathsep.join((str(tooling / "learning-python"), str(ROOT))), PYTHONNOUSERSITE="1",
               OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    budget = protocol["budget"]
    with RunLease(cache, policy, budget["max_output_bytes_per_run"]):
        admit(cache, protocol, request)
        if kind == "transfer":
            require_transfer(cache, protocol, original)
        writer = RunWriter(cache / ("state-repr-" + observation + "-" + kind + "-" + uuid.uuid4().hex[:10]),
                           budget["max_output_bytes_per_run"], budget["max_wall_seconds_per_run"])
        directory = writer.directory
        writer.write_json("protocol.json", protocol)
        writer.write_json("request.json", request)
        refit = reservation(protocol, request)["affine_fit_examples"] > 0
        for name, status in (("fitting", "not_started" if kind in {"fit", "injection"} or refit else "not_applicable"),
                             ("verification", "not_started"), ("resource", "admitted")):
            write(directory, name + "-status.json", {"status": status})
        start, error, monitor = time.monotonic(), None, None
        try:
            monitor = supervisor.supervised([sys.executable, "-B", "-m", "noetloom.state_rep_worker", str(directory)], env,
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
                raise ContractError("representation final source, time, memory, work or output check failed")
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
        result = {"schema_version": "noetloom.state_rep_run.v1", "status": "failed" if error or resource_error else "passed",
                  "kind": kind, "observation": observation, "source": source, "source_commit": head,
                  "usage": usage, "monitor": monitor, "error": error, "resource_error": resource_error,
                  "outcomes": {name: read_json(directory / (name + "-status.json")) for name in ("fitting", "verification", "resource")}}
        result["artifacts"] = supervisor.artifacts(directory)
        write(directory, "manifest.json", result)
        return {"directory": str(directory), "status": result["status"], "seconds": seconds,
                "manifest_sha256": file_digest(directory / "manifest.json"), "outcomes": result["outcomes"]}


def summary():
    cache, protocol = validate_cache(default_cache(), ROOT), read_json(PROTOCOL)
    attempts = []
    for directory, request in records(cache):
        value = read_json(directory / "manifest.json") if (directory / "manifest.json").is_file() else {}
        fit = read_json(directory / "fit.json") if request["kind"] == "fit" and (directory / "fit.json").is_file() else {}
        attempts.append({"run": directory.name, **{key: request[key] for key in ("kind", "observation", "arm", "condition", "seed")},
                         "status": value.get("status", "incomplete"), "usage": value.get("usage"),
                         "acquisition_passed": fit.get("acquisition_passed"),
                         "stages": {stage: {"gate": row["acquisition"], "selected": row["measurements"][row["selected_index"]]}
                                    for stage, row in fit.get("stages", {}).items()}})
    return {"attempts": attempts, "selections": {observation: {arm: selection(cache, protocol, observation, arm)
            for arm in protocol["arms"]} for observation in protocol["observations"]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "train", "affine", "inject", "transfer", "verify", "summary"))
    parser.add_argument("--observation", choices=("aligned", "nonlinear"))
    parser.add_argument("--arm", choices=("latent", "consistent", "direct"))
    parser.add_argument("--condition", choices=("lr003", "lr010"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--recovery", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "summary":
            result = summary()
        elif args.command == "inject":
            if any(value is not None for value in (args.observation, args.arm, args.condition, args.seed, args.run)) or args.recovery:
                raise ContractError("injection uses one fixed synthetic identity")
            result = execute("injection", observation="aligned", arm="latent", condition="lr003", seed=180797, admission=args.admission)
            if tuple(result["outcomes"][name]["status"] for name in ("fitting", "verification", "resource")) != ("completed", "failed", "completed"):
                raise ContractError("post-fit injection did not preserve required independent outcomes")
            result["expected_failure_verified"] = True
        else:
            result = execute({"train": "fit", "verify": "replay"}.get(args.command, args.command),
                             observation=args.observation, arm=args.arm, condition=args.condition, seed=args.seed,
                             admission=args.admission, original=args.run, recovery=args.recovery)
        print(json.dumps(result, indent=2))
        return int(result.get("status") == "failed" and not result.get("expected_failure_verified"))
    except (ContractError, OSError, KeyError, ValueError) as error:
        print(json.dumps({"status": "refused_or_failed", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
