"""No-network CLI for Noetloom's research foundation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .contracts import (POLICY_FILES, ContractError, check_repository, load_policy,
                        next_item, read_json, validate_plan)
from .runner import run_experiment, verify_run
from .storage import StorageError, default_cache, storage_snapshot, validate_cache

REPO_ROOT = Path(__file__).resolve().parent.parent


def _memory_bytes() -> int | None:
    try:
        if sys.platform == "darwin":
            result = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True,
                                    text=True, timeout=3, check=True)
            return int(result.stdout)
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def doctor(root: Path, cache: Path, *, profile: str = "local-small") -> dict[str, Any]:
    policy = load_policy(root, profile)
    cache = validate_cache(cache, root)
    snapshot = storage_snapshot(cache, policy, policy["max_run_output_bytes"])
    return {
        "status": "ready", "python": sys.version.split()[0], "physical_memory_bytes": _memory_bytes(),
        "cache": str(cache), "cache_exists": cache.exists(), "policy": policy,
        "storage": snapshot, "writes_performed": False, "network_required": False,
        "scope": "bootstrap harness admission; does not inspect optional training backends or enforce an OS memory sandbox",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="noetloom", description="Noetloom research control plane (no trained model).")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="read the single active queue and next executable item")
    sub.add_parser("check", help="validate contracts, references, source syntax and repo file budgets")
    inspect = sub.add_parser("doctor", help="read-only host and storage admission check")
    inspect.add_argument("--cache", type=Path, default=default_cache())
    run = sub.add_parser("run", help="execute an admitted local harness protocol")
    run.add_argument("protocol", type=Path)
    run.add_argument("--cache", type=Path, default=default_cache())
    verify = sub.add_parser("verify-run", help="verify artifact bytes and replay all harness predictions")
    verify.add_argument("directory", type=Path)
    for command in (inspect, run, verify):
        command.add_argument("--profile", choices=POLICY_FILES, default="local-small",
                             help="explicit resource policy (default: local-small)")
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            plan = read_json(REPO_ROOT / "docs/state/plan.json")
            validate_plan(plan, REPO_ROOT)
            payload = {"status": "ok", "next": next_item(plan),
                       "items": [{key: item[key] for key in ("id", "title", "status", "depends_on")}
                                 for item in plan["items"]]}
        elif args.command == "check":
            payload = check_repository(REPO_ROOT)
        elif args.command == "doctor":
            payload = doctor(REPO_ROOT, args.cache, profile=args.profile)
        elif args.command == "run":
            payload = run_experiment(REPO_ROOT, args.protocol, args.cache, profile=args.profile)
        else:
            payload = verify_run(REPO_ROOT, args.directory, profile=args.profile)
        print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
        return 1 if payload.get("status") == "failed" or payload.get("harness_verdict") == "failed" else 0
    except (ContractError, OSError, subprocess.SubprocessError, SyntaxError) as exc:
        code = "storage_refused" if isinstance(exc, StorageError) else "validation_failed"
        print(json.dumps({"status": "error", "code": code, "message": str(exc)}), file=sys.stderr)
        return 2
