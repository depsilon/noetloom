"""Immutable acquisition and solver registration for EXP-0009."""
from __future__ import annotations

import hashlib

from .contracts import ContractError, canonical_bytes

PROTOCOL_SHA256 = "e0ec54479e0879e31cbedba2788d5401f4eac110b27c0d9718d0249462250e8c"


def validate_protocol(protocol: dict, policy: dict) -> None:
    if not isinstance(protocol, dict) or hashlib.sha256(canonical_bytes(protocol)).hexdigest() != PROTOCOL_SHA256:
        raise ContractError("frozen affine-coordinate registration differs")
    budget = protocol["budget"]
    if (policy["profile"] != "local-calibration" or budget["max_wall_seconds_per_run"] > policy["max_wall_seconds"]
            or budget["max_output_bytes_per_run"] > policy["max_run_output_bytes"]
            or budget["max_presentations_per_run"] > policy["max_cases"]):
        raise ContractError("resource policy does not admit affine-coordinate acquisition")
