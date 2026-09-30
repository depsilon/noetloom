#!/usr/bin/env python3
"""Admitted Rust checks and a restartable fixture; no training or benchmarks."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from noetloom.contracts import ContractError, canonical_bytes, load_policy  # noqa: E402
from noetloom.storage import (RunLease, RunWriter, StorageError, default_cache, file_digest,
                              storage_snapshot, tree_bytes, validate_cache)  # noqa: E402

BUILD_LIMIT = 4 * 1024**3
DEPENDENCY_LIMIT = 512 * 1024**2
RUN_RESERVATION = 10 * 1024**2
BUILD_SECONDS = 300


def rust_source() -> dict:
    crate = ROOT / "crates/noetloom-core"
    paths = [ROOT / "Cargo.toml", ROOT / "Cargo.lock", ROOT / "rust-toolchain.toml",
             crate / "Cargo.toml", *crate.rglob("*.rs")]
    entries = []
    for path in sorted(paths):
        if path.is_symlink() or not path.is_file():
            raise StorageError("Rust source inventory requires regular files")
        entries.append([path.relative_to(ROOT).as_posix(), file_digest(path)])
    encoded = json.dumps(entries, separators=(",", ":")).encode()
    return {"source_files": entries, "source_sha256": hashlib.sha256(encoded).hexdigest()}


def tooling_environment() -> tuple[Path, dict[str, str]]:
    tooling = validate_cache(Path(os.environ.get("NOETLOOM_TOOLING_CACHE",
                                                str(Path.home() / ".cache/noetloom-tooling"))), ROOT)
    tooling.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(CARGO_TARGET_DIR=str(tooling / "cargo-target"),
               CARGO_HOME=str(tooling / "cargo-home"), CARGO_BUILD_JOBS="2",
               CARGO_INCREMENTAL="0", PYTHONDONTWRITEBYTECODE="1")
    return tooling, env


def check_tooling(tooling: Path, min_free: int, *, reserve: bool = False,
                  live: bool = False) -> dict[str, int]:
    build = tree_bytes(tooling / "cargo-target", live=live)
    dependencies = tree_bytes(tooling / "cargo-home", live=live)
    if build > BUILD_LIMIT or dependencies > DEPENDENCY_LIMIT:
        raise StorageError("Rust tooling exceeds admitted build/dependency storage; inspect before retrying")
    remaining = BUILD_LIMIT + DEPENDENCY_LIMIT - build - dependencies if reserve else 0
    free = shutil.disk_usage(tooling).free
    if free < min_free + remaining:
        raise StorageError("insufficient free disk for Rust tooling and required headroom")
    return {"build_bytes": build, "dependency_bytes": dependencies, "free_disk_bytes": free}


def cargo(arguments: list[str], env: dict[str, str], tooling: Path, policy: dict) -> None:
    started = time.monotonic()
    process = subprocess.Popen(["cargo", *arguments], cwd=ROOT, env=env, start_new_session=True)
    try:
        while True:
            try:
                code = process.wait(timeout=1)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() - started > BUILD_SECONDS:
                    raise StorageError("Rust command exceeded the 300-second build deadline")
                check_tooling(tooling, policy["min_free_disk_bytes"], live=True)
        if code:
            raise StorageError(f"cargo {' '.join(arguments)} failed with exit {code}")
        check_tooling(tooling, policy["min_free_disk_bytes"])
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


def fixture_output(binary: Path, command: str, state: Path, expected_source: dict) -> dict:
    result = subprocess.run([str(binary), command, str(state)], cwd=ROOT, capture_output=True,
                            timeout=15, check=False)
    if result.returncode:
        raise StorageError(f"Rust fixture {command} failed: {result.stderr[:4096].decode(errors='replace')}")
    if len(result.stdout) > 256 * 1024:
        raise StorageError("fixture receipt exceeds 256 KiB")
    receipt = json.loads(result.stdout)
    for key, value in expected_source.items():
        if receipt.get("build", {}).get(key) != value:
            raise StorageError("compiled Rust identity differs from current source; rebuild before running")
    return receipt


def run_fixture(cache: Path, tooling: Path, env: dict[str, str], policy: dict) -> dict:
    cargo(["build", "--workspace", "--example", "foundation", "--locked"], env, tooling, policy)
    binary = tooling / "cargo-target/debug/examples/foundation"
    binary_sha256 = file_digest(binary)
    expected_source = rust_source()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("foundation-%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    writer = RunWriter(cache / run_id, 2 * 1024**2, 40)
    state = writer.directory / "state"
    try:
        run = fixture_output(binary, "run", state, expected_source)
        writer.write_json("execution.json", run)
        restart = fixture_output(binary, "verify", state, expected_source)
        writer.write_json("restart.json", restart)
        if restart["snapshot"] != run["execution"]["commit"]["after"] or restart["value"] != run["emitted_value"]:
            raise StorageError("independent restart differs from committed execution")
        if rust_source() != expected_source or file_digest(binary) != binary_sha256:
            raise StorageError("source or executable changed during fixture")
        if tree_bytes(writer.directory) > RUN_RESERVATION:
            raise StorageError("fixture exceeds its total reserved output")
        artifacts = [{"path": path.relative_to(writer.directory).as_posix(),
                      "bytes": path.stat().st_size, "sha256": file_digest(path)}
                     for path in sorted(writer.directory.rglob("*")) if path.is_file()]
        manifest = {
            "schema": "noetloom.foundation_evidence.v1", "status": "passed",
            "training_performed": False, "source": expected_source,
            "binary_sha256": binary_sha256, "driver_sha256": file_digest(Path(__file__)),
            "resource_policy": policy, "tooling": check_tooling(tooling, policy["min_free_disk_bytes"]),
            "artifacts": artifacts,
            "verification_scope": "One scripted Rust execution and a separate-process restart; artifact hashing includes inactive payloads after execution, not as cognition.",
        }
        result_summary = {"status": "passed", "directory": str(writer.directory),
                "source_sha256": expected_source["source_sha256"],
                "execution_metrics": run["execution"]["metrics"],
                "snapshot": restart["snapshot"], "training_performed": False}
        completion_reservation = len(canonical_bytes(manifest)) + 65_536
        if tree_bytes(writer.directory) + completion_reservation > RUN_RESERVATION:
            raise StorageError("completion marker exceeds fixture reservation")
        storage_snapshot(cache, policy, completion_reservation)
        # Publish the success marker only after all final validation has passed.
        writer.write_json("manifest.json", manifest)
        return result_summary
    except Exception as error:
        try:
            writer.write_json("failure.json", {"status": "failed", "error": str(error)})
        except (OSError, StorageError):
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "fixture"))
    parser.add_argument("--profile", choices=("local-small", "ci-smoke"), default="local-small")
    args = parser.parse_args()
    try:
        policy = load_policy(ROOT, args.profile)
        cache = validate_cache(default_cache(), ROOT)
        tooling, env = tooling_environment()
        check_tooling(tooling, policy["min_free_disk_bytes"], reserve=True)
        with RunLease(cache, policy, RUN_RESERVATION):
            if args.command == "check":
                for command in (["fmt", "--all", "--", "--check"],
                                ["test", "--workspace", "--all-targets", "--locked"],
                                ["clippy", "--workspace", "--all-targets", "--locked", "--", "-D", "warnings"]):
                    cargo(command, env, tooling, policy)
                result = {"status": "passed", "checks": ["fmt", "test", "clippy"],
                          "tooling": check_tooling(tooling, policy["min_free_disk_bytes"])}
            else:
                result = run_fixture(cache, tooling, env, policy)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ContractError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
