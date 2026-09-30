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


def plan_fixture() -> dict:
    """A fixed dependency graph, independent of the changing project work queue."""
    return {
        "schema_version": "noetloom.plan.v1",
        "items": [
            {
                "id": f"N-{number:03d}", "title": f"Fixture item {number}", "status": "planned",
                "depends_on": [] if number == 1 else [f"N-{number - 1:03d}"],
                "sources": ["AGENTS.md"], "outcome": "Known test outcome",
                "acceptance": ["Known test condition"], "verification": ["test command"],
                "budget_profile": "local-small", "stop_condition": "Fixture complete",
                "evidence": [],
            }
            for number in (1, 2, 3)
        ],
    }
