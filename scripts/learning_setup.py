#!/usr/bin/env python3
"""Install a bounded, isolated development backend from official binary wheels."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import uuid
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noetloom.contracts import canonical_bytes, load_policy, read_json
from noetloom.storage import (RunLease, StorageError, default_cache, file_digest,
                              storage_snapshot, tree_bytes, validate_cache)

INSTALLED_LIMIT = 1024**3
DOWNLOAD_LIMIT = 256 * 1024**2


def environment() -> tuple[Path, dict[str, str]]:
    base = validate_cache(Path(os.environ.get("NOETLOOM_TOOLING_CACHE",
                                               str(Path.home() / ".cache/noetloom-tooling"))), ROOT)
    base.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(PYTHONPATH=str(base / "learning-python"), PYTHONDONTWRITEBYTECODE="1",
               PIP_DISABLE_PIP_VERSION_CHECK="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    return base, env


def setup(resume: Path | None = None) -> dict:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise StorageError("this setup admission is for macOS arm64; register another platform first")
    policy = load_policy(ROOT)
    base, env = environment()
    target, scratch = base / "learning-python", base / "learning-downloads"
    if target.exists():
        raise StorageError("learning-python already exists; inspect its setup manifest instead of overwriting")
    cache = validate_cache(default_cache(), ROOT)
    if resume is not None:
        resume = resume.resolve()
        if resume.parent != cache or not (resume / "failure.json").is_file():
            raise StorageError("resume must identify a failed setup in this cache")
    reserved = INSTALLED_LIMIT + DOWNLOAD_LIMIT + 1024**2
    if shutil.disk_usage(base).free < policy["min_free_disk_bytes"] + reserved:
        raise StorageError("backend setup lacks reserved space plus normal disk headroom")
    with RunLease(cache, policy, 1024**2):
        run_id = dt.datetime.now(dt.timezone.utc).strftime("learning-setup-%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
        directory = cache / run_id
        directory.mkdir(exist_ok=False)
        scratch.mkdir(exist_ok=resume is not None)
        env["TMPDIR"] = str(scratch)
        started = time.monotonic()

        def usage() -> tuple[int, int]:
            # pip --target stages installed files under TMPDIR before moving them.
            # Classify each directory once: subtracting two live tree scans races growth.
            installed, downloads = tree_bytes(target), 0
            for path in scratch.iterdir():
                if not path.is_dir() or path.is_symlink():
                    raise StorageError("unexpected entry in owned installation scratch")
                size = tree_bytes(path)
                if path.name.startswith("pip-target-"):
                    installed += size
                else:
                    downloads += size
            return installed, downloads

        def command(arguments: list[str], name: str) -> None:
            with (directory / name).open("xb") as log:
                child = subprocess.Popen(arguments, env=env, cwd=ROOT, stdout=log,
                                         stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    while child.poll() is None:
                        if time.monotonic() - started > 300:
                            raise StorageError("backend setup exceeded 300 seconds")
                        installed, downloads = usage()
                        if installed > INSTALLED_LIMIT or downloads > DOWNLOAD_LIMIT:
                            raise StorageError("backend setup exceeded installed/download admission")
                        if tree_bytes(directory) > 1024**2:
                            raise StorageError("backend setup log exceeded 1 MiB")
                        storage_snapshot(cache, policy)
                        time.sleep(0.25)
                    if child.returncode:
                        raise StorageError(f"backend setup failed; inspect {directory / name}")
                finally:
                    if child.poll() is None:
                        os.killpg(child.pid, signal.SIGTERM)
                        try:
                            child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid, signal.SIGKILL)
                            child.wait()

        try:
            common = [sys.executable, "-B", "-m", "pip", "--isolated", "install", "--disable-pip-version-check",
                      "--index-url", "https://pypi.org/simple", "--only-binary=:all:", "--no-cache-dir",
                      "--ignore-installed", "--no-compile", "--target", str(target)]
            report_path = directory / "resolution.json"
            if resume is None:
                command([*common, "--dry-run", "--report", str(report_path), "torch==2.14.0"], "resolve.log")
            else:
                report_path.write_bytes((resume / "resolution.json").read_bytes())
            report = read_json(report_path, 1024**2)
            requirements = []
            wheels = []
            for package in report["install"]:
                download = package["download_info"]
                url = urlparse(download["url"])
                if url.scheme != "https" or url.netloc != "files.pythonhosted.org" or not url.path.endswith(".whl"):
                    raise StorageError("resolution includes a non-PyPI wheel or source build")
                digest = download["archive_info"]["hashes"]["sha256"]
                name, version = package["metadata"]["name"], package["metadata"]["version"]
                requirements.append(f"{name}=={version} --hash=sha256:{digest}")
                wheels.append({"name": name, "version": version, "url": download["url"], "sha256": digest})
            lock = directory / "requirements.txt"
            lock.write_text("\n".join(requirements) + "\n")
            offline = []
            if resume is not None:
                expected = {wheel["sha256"] for wheel in wheels}
                found = set()
                for path in scratch.glob("*/*.whl"):
                    digest = file_digest(path)
                    if digest in expected:
                        found.add(digest)
                        offline.extend(["--find-links", str(path.parent)])
                if found != expected:
                    raise StorageError("failed setup does not retain every verified wheel for offline recovery")
                offline.append("--no-index")
            command([*common, *offline, "--require-hashes", "-r", str(lock)], "install.log")
            command([sys.executable, "-B", "-c",
                     "import json,torch; print(json.dumps({'torch':torch.__version__,'cuda':torch.cuda.is_available(),'threads':torch.get_num_threads()})); assert torch.__version__ == '2.14.0'"], "import.log")
            installed, downloads = usage()
            if installed > INSTALLED_LIMIT or downloads > DOWNLOAD_LIMIT:
                raise StorageError("backend setup final storage admission failed")
            storage_snapshot(cache, policy)
            manifest = {"schema_version": "noetloom.learning_setup.v1", "status": "passed", "wheels": wheels,
                        "python": sys.version, "platform": platform.platform(), "target": str(target),
                        "installed_bytes": installed, "download_bytes": downloads,
                        "resumed_from": str(resume) if resume else None,
                        "elapsed_seconds": time.monotonic() - started, "driver_sha256": file_digest(Path(__file__)),
                        "artifacts": [{"path": p.name, "sha256": file_digest(p), "bytes": p.stat().st_size}
                                      for p in sorted(directory.iterdir()) if p.is_file()]}
            (directory / "manifest.json").write_bytes(canonical_bytes(manifest))
            return {"status": "passed", "directory": str(directory), "target": str(target),
                    "installed_bytes": manifest["installed_bytes"], "wheels": len(wheels)}
        except Exception as error:
            (directory / "failure.json").write_bytes(canonical_bytes({"status": "failed", "error": str(error)}))
            raise


if __name__ == "__main__":
    try:
        import argparse
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--resume", type=Path)
        print(json.dumps(setup(parser.parse_args().resume), sort_keys=True))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
        raise SystemExit(1)
