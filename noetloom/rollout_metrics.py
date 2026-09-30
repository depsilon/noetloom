"""Exact-prefix metrics for saved binary transition rollouts."""
from __future__ import annotations

import math
from numbers import Real
from typing import Any

from .contracts import ContractError


def _validate_inputs(rows: Any, logits: Any) -> None:
    if not isinstance(rows, list) or not isinstance(logits, list):
        raise ContractError("rows and logits must be lists")
    if len(rows) != len(logits):
        raise ContractError("row and logit trajectory counts differ")
    for index, (row, trajectory) in enumerate(zip(rows, logits)):
        where = f"trajectory {index}"
        if not isinstance(row, dict):
            raise ContractError(f"{where} must be an object")
        actions = row.get("actions")
        targets = row.get("targets")
        family = row.get("family")
        if not isinstance(actions, list) or not actions:
            raise ContractError(f"{where} actions must be a nonempty list")
        if any(type(action) is not int or action < 0 or action > 3 for action in actions):
            raise ContractError(f"{where} actions must be integers in [0, 3]")
        if not isinstance(family, str) or not family.strip():
            raise ContractError(f"{where} family must be a nonempty string")
        if not isinstance(targets, list) or len(targets) != len(actions):
            raise ContractError(f"{where} needs one target state per action")
        if not isinstance(trajectory, list) or len(trajectory) != len(actions):
            raise ContractError(f"{where} needs one logit state per action")
        for step, (target, values) in enumerate(zip(targets, trajectory), start=1):
            if (not isinstance(target, list) or len(target) != 8
                    or any(type(bit) is not int or bit not in (0, 1) for bit in target)):
                raise ContractError(f"{where} target at step {step} must be an 8-bit list")
            if not isinstance(values, list) or len(values) != 8:
                raise ContractError(f"{where} logits at step {step} must contain 8 values")
            for value in values:
                try:
                    finite = math.isfinite(value) if not isinstance(value, bool) and isinstance(value, Real) else False
                except (OverflowError, TypeError, ValueError):
                    finite = False
                if not finite:
                    raise ContractError(f"{where} logits must be finite numeric non-bool values")


def prefix_metrics(rows: list[dict], logits: list[list[list[float]]]) -> dict[str, dict]:
    """Score every predicted prefix and aggregate by trajectory, length, action and family.

    A prefix is exact when all eight predicted bits at that step match its target.
    ``all_prefix_exact`` counts trajectories whose every prefix is exact; ``final_exact``
    counts only correct endpoints and therefore does not imply full rollout success.
    """
    _validate_inputs(rows, logits)
    if not rows:
        return {}

    groups: dict[str, dict[str, Any]] = {}

    def group_for(key: str) -> dict[str, Any]:
        if key not in groups:
            groups[key] = {
                "cases": 0,
                "prefixes": 0,
                "exact_prefixes": 0,
                "all_prefix_exact": 0,
                "final_exact": 0,
                "first_error_step": {},
                "ever_recovered": 0,
                "final_recovered": 0,
                "steps": {},
            }
        return groups[key]

    for row, trajectory in zip(rows, logits):
        actions = row["actions"]
        targets = row["targets"]
        predictions = [[int(value >= 0) for value in state] for state in trajectory]
        exact_steps = [prediction == target for prediction, target in zip(predictions, targets)]
        first_error = next((i for i, exact in enumerate(exact_steps, start=1) if not exact), None)
        recovered = any(not exact_steps[i] and any(exact_steps[i + 1:])
                        for i in range(len(exact_steps)))
        final_exact = exact_steps[-1]
        keys = ("all", f"length/{len(actions)}", f"action/{actions[-1]}", f"family/{row['family']}")

        for key in keys:
            group = group_for(key)
            group["cases"] += 1
            group["prefixes"] += len(actions)
            group["exact_prefixes"] += sum(exact_steps)
            group["all_prefix_exact"] += int(all(exact_steps))
            group["final_exact"] += int(final_exact)
            error_key = "none" if first_error is None else str(first_error)
            errors = group["first_error_step"]
            errors[error_key] = errors.get(error_key, 0) + 1
            group["ever_recovered"] += int(recovered)
            group["final_recovered"] += int(first_error is not None and final_exact)
            for step, exact in enumerate(exact_steps, start=1):
                step_metrics = group["steps"].setdefault(str(step), {"cases": 0, "exact": 0})
                step_metrics["cases"] += 1
                step_metrics["exact"] += int(exact)

    result = {}
    for key in sorted(groups):
        group = groups[key]
        group["first_error_step"] = dict(sorted(
            group["first_error_step"].items(),
            key=lambda item: (item[0] == "none", 0 if item[0] == "none" else int(item[0]))))
        group["steps"] = dict(sorted(group["steps"].items(), key=lambda item: int(item[0])))
        group["prefix_exact_accuracy"] = group["exact_prefixes"] / group["prefixes"]
        group["all_prefix_exact_accuracy"] = group["all_prefix_exact"] / group["cases"]
        group["final_exact_accuracy"] = group["final_exact"] / group["cases"]
        result[key] = group
    return result
