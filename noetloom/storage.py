"""Bounded local artifact writes; no network transfer or automatic eviction."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path
from typing import Any, BinaryIO

from .contracts import ContractError, canonical_bytes


class StorageError(ContractError):
    """Storage admission, ownership, or a run budget failed."""


def default_cache() -> Path:
    return Path(os.environ.get("NOETLOOM_CACHE", str(Path.home() / ".cache/noetloom"))).expanduser()


def _inside(path: Path, parent: Path) -> bool:
    # macOS commonly uses case-insensitive APFS. Reject lexical aliases as well.
    left = tuple(part.casefold() for part in path.parts)
    right = tuple(part.casefold() for part in parent.parts)
    return left[:len(right)] == right


def validate_cache(path: Path, repo_root: Path, *, home: Path | None = None,
                   platform: str | None = None) -> Path:
    home = (home or Path.home()).resolve()
    lexical = Path(os.path.abspath(path.expanduser()))
    resolved = lexical.resolve()
    repo = repo_root.resolve()
    macos = (platform or sys.platform) == "darwin"
    contains = _inside if macos else lambda child, parent: child.is_relative_to(parent)
    if (contains(resolved, home) and contains(home, resolved)) or resolved == Path(resolved.anchor):
        raise StorageError("use a dedicated Noetloom cache directory")
    if contains(resolved, repo) or contains(repo, resolved):
        raise StorageError("run storage must be outside the checkout and its ancestors")
    if macos:
        forbidden = [home / "Desktop", home / "Documents", home / "Library/Mobile Documents",
                     home / "Library/CloudStorage", home / "Library/Application Support/CloudDocs"]
        for parent in forbidden:
            if any(_inside(candidate, boundary) for candidate in (lexical, resolved)
                   for boundary in (parent, parent.resolve())):
                raise StorageError("bulk run output must be outside Documents/Desktop and cloud storage")
    if resolved.exists() and not resolved.is_dir():
        raise StorageError("cache path is not a directory")
    return resolved


def tree_bytes(root: Path, *, live: bool = False) -> int:
    """Count allocated bytes, deduplicate hardlinks, and refuse symlinks/special files.

    Live sampling tolerates entries disappearing between enumeration and lstat, such as
    an atomically renamed state pointer. It is not a consistent filesystem snapshot.
    Admission, artifact inventories and completion use the strict default after writers stop.
    """
    if not root.exists():
        return 0
    total = 0
    count = 0
    seen: set[tuple[int, int]] = set()

    def on_error(error: OSError) -> None:
        if live and isinstance(error, FileNotFoundError):
            return
        raise StorageError(f"cannot account for cache contents: {error}") from error

    for parent, directories, files in os.walk(root, followlinks=False, onerror=on_error):
        for name in directories + files:
            path = Path(parent) / name
            count += 1
            if count > 100000:
                raise StorageError("cache inventory exceeds 100000 entries; inspect before running")
            try:
                info = path.lstat()
            except FileNotFoundError:
                if live:
                    continue
                raise
            if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise StorageError(f"unaccountable cache entry: {path.name}")
            if stat.S_ISREG(info.st_mode):
                identity = (info.st_dev, info.st_ino)
                if identity not in seen:
                    seen.add(identity)
                    total += max(info.st_size, getattr(info, "st_blocks", 0) * 512)
    return total


def storage_snapshot(root: Path, policy: dict[str, Any], reserve_bytes: int = 0,
                     *, live: bool = False) -> dict[str, int]:
    if type(reserve_bytes) is not int or reserve_bytes < 0:
        raise StorageError("reservation must be a nonnegative integer")
    ancestor = root
    while not ancestor.exists():
        ancestor = ancestor.parent
    free = shutil.disk_usage(ancestor).free
    used = tree_bytes(root, live=live)
    if used + reserve_bytes > policy["max_workspace_bytes"]:
        raise StorageError("cache plus output reservation exceeds workspace budget")
    if free < policy["min_free_disk_bytes"] + reserve_bytes:
        raise StorageError("insufficient free disk after output reservation and headroom")
    return {"workspace_bytes": used, "free_disk_bytes": free, "reserved_bytes": reserve_bytes}


class RunLease:
    """Exclusive writer admission. Existing locks are never presumed stale."""

    def __init__(self, root: Path, policy: dict[str, Any], reserve_bytes: int):
        self.root = root
        self.policy = policy
        self.reserve_bytes = reserve_bytes
        self.lock = root / ".noetloom-run.lock"
        self.identity: tuple[int, int] | None = None

    def __enter__(self) -> "RunLease":
        storage_snapshot(self.root, self.policy, self.reserve_bytes)
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise StorageError("a run lock exists; inspect its owner before removing it") from exc
        try:
            info = os.fstat(fd)
            self.identity = (info.st_dev, info.st_ino)
            os.write(fd, canonical_bytes({"pid": os.getpid(), "started_unix": time.time()}))
            os.fsync(fd)
        except BaseException:
            self._release()
            raise
        finally:
            os.close(fd)
        try:
            # Recheck after acquiring the writer lock to close the admission race.
            storage_snapshot(self.root, self.policy, self.reserve_bytes)
        except BaseException:
            self._release()
            raise
        return self

    def _release(self) -> None:
        try:
            info = self.lock.lstat()
            if self.identity == (info.st_dev, info.st_ino):
                self.lock.unlink()
        except FileNotFoundError:
            pass

    def __exit__(self, *_: Any) -> None:
        self._release()


class RunWriter:
    """New files only, bounded bytes, and a cooperative wall-clock deadline."""

    def __init__(self, directory: Path, max_bytes: int, max_seconds: int):
        self.directory = directory
        self.max_bytes = max_bytes
        self.max_seconds = max_seconds
        self.bytes_written = 0
        self.started = time.monotonic()
        directory.mkdir(exist_ok=False)

    def checkpoint(self) -> None:
        if time.monotonic() - self.started > self.max_seconds:
            raise StorageError("run wall-clock budget exceeded")

    def append(self, handle: BinaryIO, payload: bytes) -> None:
        self.checkpoint()
        if self.bytes_written + len(payload) > self.max_bytes:
            raise StorageError("run output-byte budget exceeded")
        handle.write(payload)
        self.bytes_written += len(payload)

    def write_json(self, name: str, payload: Any) -> None:
        if Path(name).name != name or name in {".", ".."}:
            raise StorageError("artifact name must be a single filename")
        with (self.directory / name).open("xb") as handle:
            self.append(handle, canonical_bytes(payload))


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_identity(repo_root: Path) -> dict[str, Any]:
    entries = []
    for path in sorted((repo_root / "noetloom").glob("*.py")):
        if path.is_symlink():
            raise StorageError("runtime source must not be symlinked")
        entries.append({"path": path.relative_to(repo_root).as_posix(), "sha256": file_digest(path)})
    if not entries:
        raise StorageError("runtime source inventory is empty")
    return {
        "schema_version": "noetloom.source.v1",
        "files": entries,
        "digest": hashlib.sha256(canonical_bytes(entries)).hexdigest(),
    }
