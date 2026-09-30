"""Immutable scientific scope and resource admission for EXP-0008."""
from __future__ import annotations

import hashlib

from .contracts import ContractError, canonical_bytes

PROTOCOL_SHA256 = "f38f10140380dd436aecb62ed9caeebc344b8f0417d6d5eab16b68e6a2985849"


def validate_protocol(protocol: dict, policy: dict) -> None:
    if not isinstance(protocol, dict) or hashlib.sha256(canonical_bytes(protocol)).hexdigest() != PROTOCOL_SHA256:
        raise ContractError("frozen coordinate acquisition registration differs")
    budget = protocol["budget"]
    if (policy["profile"] != "local-calibration" or budget["max_wall_seconds_per_run"] > policy["max_wall_seconds"]
            or budget["max_output_bytes_per_run"] > policy["max_run_output_bytes"]
            or budget["max_presentations_per_run"] > policy["max_cases"]):
        raise ContractError("resource policy does not admit coordinate acquisition")
