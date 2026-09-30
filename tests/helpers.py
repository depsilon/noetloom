from __future__ import annotations

import copy
from pathlib import Path

from noetloom.contracts import canonical_bytes, read_json

ROOT = Path(__file__).resolve().parent.parent


def policy() -> dict:
    return read_json(ROOT / "config/resource-policy.json")


def protocol() -> dict:
    return read_json(ROOT / "experiments/EXP-0001/protocol.json")


def small_protocol() -> dict:
    value = copy.deepcopy(protocol())
    value["seeds"] = value["seeds"][:2]
    value["splits"] = value["splits"][:3]
    for split in value["splits"]:
        split["episodes"] = 1
    value["budget"] = {"max_wall_seconds": 5, "max_output_bytes": 1024 * 1024}
    return value


def write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_bytes(value))
