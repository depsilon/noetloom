#!/usr/bin/env python3
"""Prepare and inspect bounded evidence bundles; no upload or local retirement."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noetloom.contracts import ContractError, canonical_bytes, load_policy, read_json
from noetloom.storage import RunLease, default_cache, file_digest, storage_snapshot, tree_bytes, validate_cache

LIMIT = 512 * 1024**2
PRIOR = ("572f2fc4eb8c6beb866d981458526f368fc19141", "bd7c1b051fa1621608cdb20b1049e010e7aed216",
         "293a9578f9ed5a700be3d4d6e43a7308d1fbe598")


def pack(scope: str) -> dict:
    cache, policy = validate_cache(default_cache(), ROOT), load_policy(ROOT)
    prefixes = {"prior": ("learning-", "allocation-", "representation-"),
                "calibration": ("calibration-",), "transitions": ("transitions-",),
                "transition-diagnostics": ("transition-diagnostic-",),
                "state-repr-aligned": ("state-repr-aligned-",),
                "state-repr-nonlinear": ("state-repr-nonlinear-",), "coordinates": ("coordinates-",),
                "affine-coordinates": ("affine-coordinates-",)}[scope]
    with RunLease(cache, policy, LIMIT):
        directories = sorted(p for p in cache.iterdir() if p.name.startswith(prefixes) and p.is_dir())
        if not directories or sum(tree_bytes(p) for p in directories) > LIMIT // 2:
            raise ContractError("backup scope empty or exceeds 256 MiB input admission")
        output = cache / ("artifact-bundle-" + scope + "-" + uuid.uuid4().hex[:8])
        output.mkdir()
        archive = output / "evidence.tar.gz"
        entries = []
        revisions = PRIOR if scope == "prior" else tuple(sorted({
            read_json(p / "request.json")["source_commit"] for p in directories if (p / "request.json").is_file()}))
        if not revisions:
            raise ContractError("bundle has no source revisions")
        with tarfile.open(archive, "w:gz") as bundle:
            for directory in directories:
                for path in sorted(directory.rglob("*")):
                    if not path.is_file():
                        continue
                    relative = "runs/" + path.relative_to(cache).as_posix()
                    bundle.add(path, arcname=relative, recursive=False)
                    entries.append({"path": relative, "bytes": path.stat().st_size, "sha256": file_digest(path)})
            for revision in revisions:
                source = subprocess.run(["git", "archive", "--format=tar", revision], cwd=ROOT,
                                        check=True, capture_output=True, timeout=30).stdout
                relative = f"sources/{revision}.tar"
                info = tarfile.TarInfo(relative)
                info.size, info.mode = len(source), 0o600
                bundle.addfile(info, io.BytesIO(source))
                import hashlib
                entries.append({"path": relative, "bytes": len(source), "sha256": hashlib.sha256(source).hexdigest()})
        inventory = {"schema_version": "noetloom.evidence_bundle.v1", "scope": scope,
                     "created_unix": time.time(), "directories": len(directories), "entries": entries,
                     "source_revisions": list(revisions), "logical_payload_bytes": sum(e["bytes"] for e in entries),
                     "archive_bytes": archive.stat().st_size, "archive_sha256": file_digest(archive),
                     "status": "staged_local_only", "retirement_authorized": False}
        (output / "inventory.json").write_bytes(canonical_bytes(inventory))
        if tree_bytes(output) > LIMIT:
            raise ContractError("staged bundle exceeded its reservation")
        storage_snapshot(cache, policy)
        return {"directory": str(output), **{k: v for k, v in inventory.items() if k != "entries"}}


def restore(archive: Path, inventory_path: Path) -> dict:
    inventory = read_json(inventory_path, 8 * 1024**2)
    if inventory.get("schema_version") != "noetloom.evidence_bundle.v1":
        raise ContractError("unsupported bundle inventory")
    if archive.stat().st_size != inventory["archive_bytes"] or file_digest(archive) != inventory["archive_sha256"]:
        raise ContractError("bundle bytes differ from the retained inventory")
    entries = inventory["entries"]
    if (len(entries) > 10000 or len({e["path"] for e in entries}) != len(entries)
            or sum(e["bytes"] for e in entries) > LIMIT):
        raise ContractError("bundle inventory exceeds admission or repeats a path")
    cache, policy = validate_cache(default_cache(), ROOT), load_policy(ROOT)
    with RunLease(cache, policy, LIMIT):
        target = cache / ("artifact-restore-" + uuid.uuid4().hex[:8])
        target.mkdir()
        expected = {e["path"]: e for e in entries}
        seen = set()
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle:
                name = PurePosixPath(member.name)
                if (member.name not in expected or member.name in seen or not member.isfile()
                        or name.is_absolute() or ".." in name.parts or "\\" in member.name
                        or member.size != expected[member.name]["bytes"]):
                    raise ContractError("unsafe, duplicate or unexpected archive member")
                path = target.joinpath(*name.parts)
                path.parent.mkdir(parents=True, exist_ok=True)
                handle = bundle.extractfile(member)
                with path.open("xb") as output:
                    while block := handle.read(1024 * 1024):
                        output.write(block)
                os.chmod(path, 0o700 if member.mode & 0o111 else 0o600)
                if file_digest(path) != expected[member.name]["sha256"]:
                    raise ContractError("restored file differs from inventory")
                seen.add(member.name)
        if seen != set(expected):
            raise ContractError("archive is missing inventoried files")
        storage_snapshot(cache, policy)
        result = {"status": "byte_inventory_verified", "directory": str(target), "files": len(seen),
                  "archive_sha256": inventory["archive_sha256"],
                  "scope": "All restored bytes; replay and independent destination still require separate evidence."}
        (target / "restore.json").write_bytes(canonical_bytes(result))
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("pack")
    create.add_argument("--scope", choices=("prior", "calibration", "transitions", "transition-diagnostics", "state-repr-aligned", "state-repr-nonlinear", "coordinates", "affine-coordinates"), required=True)
    unpack = sub.add_parser("restore")
    unpack.add_argument("--archive", type=Path, required=True)
    unpack.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = pack(args.scope) if args.command == "pack" else restore(args.archive, args.inventory)
        print(json.dumps(result, indent=2))
        return 0
    except (ContractError, OSError, tarfile.TarError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
