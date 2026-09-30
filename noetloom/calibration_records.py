"""Atomic, bounded fitting records independent of downstream verification."""
from __future__ import annotations

import os
from pathlib import Path

from .contracts import ContractError, canonical_bytes, read_json
from .storage import tree_bytes


def write(directory: Path, name: str, value: object) -> None:
    if Path(name).name != name or name in {".", ".."}:
        raise ContractError("calibration artifact needs one filename")
    payload = canonical_bytes(value)
    limit = read_json(directory / "protocol.json")["budget"]["max_output_bytes_per_run"]
    if tree_bytes(directory, live=True) + len(payload) + 65536 > limit:
        raise ContractError("calibration publication exceeds reserved output space")
    temporary = directory / ("." + name + ".tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, directory / name)


def publish_fit(directory: Path, fit: dict, verify, *, inject_failure: bool = False) -> dict:
    """Publish the fitting boundary before entering any downstream callback."""
    write(directory, "fit.json", fit)
    write(directory, "fitting-status.json", {"status": "completed", "completed_updates": fit["completed_updates"]})
    write(directory, "verification-status.json", {"status": "running"})
    try:
        if inject_failure:
            raise ContractError("registered injected post-fit verification failure")
        result = verify()
        write(directory, "verification-status.json", {"status": "completed", **result})
        return result
    except BaseException as error:
        write(directory, "verification-status.json", {"status": "failed", "error": str(error)})
        raise
