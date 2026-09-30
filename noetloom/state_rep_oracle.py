"""Exact scalar oracle fixture for the registered nonlinear-shear observation family.

This is an analytic control, not a learned candidate.  Its capacity claim is
limited to encoding and decoding the configured bipolar products and composing
the configured signed-permutation transitions.
"""
from __future__ import annotations

import math
from typing import Any

from .state_rep_data import rules
from .state_rep_model import parameter_count, shapes, validate_snapshot


def _zeros(shape: tuple[int, ...]) -> list[Any]:
    if len(shape) == 1:
        return [0.0] * shape[0]
    return [_zeros(shape[1:]) for _ in range(shape[0])]


def oracle_snapshot(config: dict[str, Any]) -> dict[str, Any]:
    """Return the 1804-parameter latent oracle snapshot for one data config.

    Every sheared target is reconstructed from its original, unchanged source
    coordinates.  This fixture intentionally has no generalized product claim.
    """
    shears = config.get("nonlinear_shears")
    coefficient = config.get("nonlinear_coefficient")
    if not isinstance(shears, (list, tuple)) or not shears:
        raise ValueError("config.nonlinear_shears must be a nonempty sequence")
    if type(coefficient) not in (int, float) or not math.isfinite(coefficient):
        raise ValueError("config.nonlinear_coefficient must be finite")
    checked: list[tuple[int, int, int]] = []
    targets: set[int] = set()
    sources: set[int] = set()
    for shear in shears:
        if not isinstance(shear, (list, tuple)) or len(shear) != 3:
            raise ValueError("each nonlinear shear must be (target, source_u, source_v)")
        target, u, v = shear
        if any(type(index) is not int or not 0 <= index < 10 for index in shear):
            raise ValueError("shear coordinates must be integers in [0, 9]")
        if u == v or target in (u, v) or target in targets:
            raise ValueError("oracle requires distinct sources and unique non-source targets")
        checked.append((target, u, v))
        targets.add(target)
        sources.update((u, v))
    if targets & sources:
        raise ValueError("oracle requires every product source coordinate to remain unchanged")
    world_seed = config.get("world_seed")
    if type(world_seed) is not int or world_seed < 0:
        raise ValueError("config.world_seed must be a nonnegative integer")

    snapshot = {"schema_version": "noetloom.state_rep_parameters.v1", "arm": "latent",
                "seed": 0, "step": 0,
                "tensors": {name: _zeros(shape) for name, shape in shapes("latent").items()}}
    tensors = snapshot["tensors"]
    alpha = 2.0 / (math.tanh(3.0) - 3.0 * math.tanh(1.0))
    beta = -1.0 - 2.0 * alpha * math.tanh(1.0)
    for i, (target, u, v) in enumerate(checked):
        # tanh(u+v+1) - tanh(u+v-1) isolates the odd-parity bipolar product.
        for unit, bias in ((2 * i, 1.0), (2 * i + 1, -1.0)):
            tensors["encoder_first_weight"][unit][u] = 1.0
            tensors["encoder_first_weight"][unit][v] = 1.0
            tensors["encoder_first_bias"][unit] = bias
            tensors["decoder_first_weight"][unit][u] = 1.0
            tensors["decoder_first_weight"][unit][v] = 1.0
            tensors["decoder_first_bias"][unit] = bias
        tensors["encoder_last_weight"][target][2 * i] = -coefficient * alpha
        tensors["encoder_last_weight"][target][2 * i + 1] = coefficient * alpha
        tensors["encoder_last_bias"][target] = -coefficient * beta
        tensors["decoder_last_weight"][target][2 * i] = coefficient * alpha
        tensors["decoder_last_weight"][target][2 * i + 1] = -coefficient * alpha
        tensors["decoder_last_bias"][target] = coefficient * beta

    for action, (permutation, mask) in enumerate(rules(world_seed)):
        for target, (source, bit) in enumerate(zip(permutation, mask)):
            tensors["transition_weight"][action][target][source] = -1.0 if bit else 1.0

    validate_snapshot(snapshot)
    assert parameter_count("latent") == 1804
    return snapshot
