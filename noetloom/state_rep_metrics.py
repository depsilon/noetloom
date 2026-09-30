"""Continuous observation and paired continuation metrics for state representations."""
from __future__ import annotations

import math
from typing import Any

from .contracts import ContractError


def _fail(where: str, message: str) -> None:
    raise ContractError(f"{where} {message}")


def _number(value: Any, where: str) -> float:
    if type(value) not in (int, float):
        _fail(where, "must be a finite numeric non-bool value")
    try:
        result = float(value)
    except OverflowError:
        _fail(where, "must be a finite numeric non-bool value")
    if not math.isfinite(result):
        _fail(where, "must be a finite numeric non-bool value")
    return result


def _tolerance(value: Any) -> float:
    result = _number(value, "tolerance")
    if result <= 0:
        _fail("tolerance", "must be positive")
    return result


def _vector(value: Any, where: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 10:
        _fail(where, "must be a ten-coordinate list")
    return [_number(item, f"{where}[{index}]") for index, item in enumerate(value)]


def _rows(rows: Any, where: str) -> None:
    if not isinstance(rows, list):
        _fail(where, "must be a list")


def _trajectory_rows(rows: list[dict], outputs: Any, where: str, action_key: str = "actions"
                     ) -> tuple[list[list[list[float]]], list[list[list[float]]]]:
    if not isinstance(outputs, list) or len(outputs) != len(rows):
        _fail(where, "trajectory count differs from rows")
    checked: list[list[list[float]]] = []
    checked_targets_by_row: list[list[list[float]]] = []
    for index, (row, trajectory) in enumerate(zip(rows, outputs)):
        label = f"{where} trajectory {index}"
        if not isinstance(row, dict):
            _fail(f"row {index}", "must be an object")
        actions, targets, family = row.get(action_key), row.get("targets"), row.get("family")
        if not isinstance(actions, list) or not actions:
            _fail(f"row {index} {action_key}", "must be a nonempty list")
        if any(type(action) is not int or not 0 <= action <= 3 for action in actions):
            _fail(f"row {index} {action_key}", "must contain integers in [0, 3]")
        if not isinstance(family, str) or not family.strip():
            _fail(f"row {index} family", "must be a nonempty string")
        if not isinstance(targets, list) or len(targets) != len(actions):
            _fail(f"row {index} targets", "must contain one observation per action")
        checked_targets = [_vector(target, f"row {index} target {step}")
                           for step, target in enumerate(targets, start=1)]
        if not isinstance(trajectory, list) or len(trajectory) != len(actions):
            _fail(label, "must contain one observation per action")
        checked_outputs = [_vector(output, f"{label} step {step}")
                           for step, output in enumerate(trajectory, start=1)]
        checked_targets_by_row.append(checked_targets)
        checked.append(checked_outputs)
    return checked, checked_targets_by_row


def _absolute_error(expected: float, actual: float, where: str) -> float:
    error = abs(actual - expected)
    if not math.isfinite(error):
        _fail(where, "error magnitude exceeds finite numeric range")
    return error


def _square(value: float, where: str) -> float:
    result = value * value
    if not math.isfinite(result):
        _fail(where, "squared error exceeds finite numeric range")
    return result


def _add_finite(total: float, value: float, where: str) -> float:
    result = total + value
    if not math.isfinite(result):
        _fail(where, "aggregate exceeds finite numeric range")
    return result


def score(rows: list[dict], outputs: list[list[list[float]]], tolerance: float = 0.25) -> dict[str, dict]:
    """Score continuous observations at every prefix and aggregate by length/action/family."""
    tol = _tolerance(tolerance)
    _rows(rows, "rows")
    checked_outputs, targets_by_row = _trajectory_rows(rows, outputs, "outputs")
    if not rows:
        return {}

    groups: dict[str, dict[str, Any]] = {}

    def group_for(key: str) -> dict[str, Any]:
        if key not in groups:
            groups[key] = {"cases": 0, "prefixes": 0, "exact_prefixes": 0,
                           "all_prefix_exact": 0, "final_exact": 0, "first_error_step": {},
                           "ever_recovered": 0, "final_recovered": 0, "steps": {},
                           "_squared_error_sum": 0.0, "_coordinate_count": 0,
                           "maximum_absolute_error": 0.0}
        return groups[key]

    for row, trajectory, targets in zip(rows, checked_outputs, targets_by_row):
        errors = [[_absolute_error(target, output, "score") for target, output in zip(expected, actual)]
                  for expected, actual in zip(targets, trajectory)]
        exact_steps = [all(error <= tol for error in step_errors) for step_errors in errors]
        first_error = next((step for step, exact in enumerate(exact_steps, start=1) if not exact), None)
        recovered = any(not exact_steps[i] and any(exact_steps[i + 1:])
                        for i in range(len(exact_steps)))
        final_exact = exact_steps[-1]
        keys = ("all", f"length/{len(trajectory)}", f"action/{row['actions'][-1]}",
                f"family/{row['family']}")
        squared = [[_square(error, "score") for error in step_errors]
                   for step_errors in errors]
        for key in keys:
            group = group_for(key)
            group["cases"] += 1
            group["prefixes"] += len(trajectory)
            group["exact_prefixes"] += sum(exact_steps)
            group["all_prefix_exact"] += int(all(exact_steps))
            group["final_exact"] += int(final_exact)
            error_key = "none" if first_error is None else str(first_error)
            group["first_error_step"][error_key] = group["first_error_step"].get(error_key, 0) + 1
            group["ever_recovered"] += int(recovered)
            group["final_recovered"] += int(first_error is not None and final_exact)
            for step, exact in enumerate(exact_steps, start=1):
                step_metrics = group["steps"].setdefault(str(step), {"cases": 0, "exact": 0})
                step_metrics["cases"] += 1
                step_metrics["exact"] += int(exact)
            flat_errors = [error for one_step in errors for error in one_step]
            for one_step in squared:
                for value in one_step:
                    group["_squared_error_sum"] = _add_finite(group["_squared_error_sum"], value, "score MSE")
            group["_coordinate_count"] += len(flat_errors)
            group["maximum_absolute_error"] = max(group["maximum_absolute_error"], *flat_errors)

    result = {}
    for key, group in sorted(groups.items()):
        group["first_error_step"] = dict(sorted(
            group["first_error_step"].items(),
            key=lambda item: (item[0] == "none", 0 if item[0] == "none" else int(item[0]))))
        group["steps"] = dict(sorted(group["steps"].items(), key=lambda item: int(item[0])))
        group["prefix_exact_accuracy"] = group["exact_prefixes"] / group["prefixes"]
        group["all_prefix_exact_accuracy"] = group["all_prefix_exact"] / group["cases"]
        group["final_exact_accuracy"] = group["final_exact"] / group["cases"]
        group["mse"] = group.pop("_squared_error_sum") / group.pop("_coordinate_count")
        if not math.isfinite(group["mse"]):
            _fail("score MSE", "aggregate exceeds finite numeric range")
        result[key] = group
    return result


def reconstruction_metrics(observations: list[list[float]], predictions: list[list[float]],
                           tolerance: float = 0.25) -> dict[str, Any]:
    """Score per-observation reconstruction fidelity without quantizing coordinates."""
    tol = _tolerance(tolerance)
    if not isinstance(observations, list) or not isinstance(predictions, list):
        _fail("observations and predictions", "must be lists")
    if len(observations) != len(predictions):
        _fail("observations and predictions", "case counts differ")
    checked_observations = [_vector(value, f"observation {i}") for i, value in enumerate(observations)]
    checked_predictions = [_vector(value, f"prediction {i}") for i, value in enumerate(predictions)]
    cases = len(observations)
    if not cases:
        return {"cases": 0, "exact": 0, "accuracy": None, "mse": None,
                "maximum_absolute_error": None}
    errors = [[_absolute_error(expected, actual, "reconstruction") for expected, actual in zip(observation, prediction)]
              for observation, prediction in zip(checked_observations, checked_predictions)]
    exact = sum(all(error <= tol for error in row) for row in errors)
    squares = [_square(error, "reconstruction") for row in errors for error in row]
    total_squared = 0.0
    for value in squares:
        total_squared = _add_finite(total_squared, value, "reconstruction MSE")
    mse = total_squared / len(squares)
    if not math.isfinite(mse):
        _fail("reconstruction MSE", "aggregate exceeds finite numeric range")
    return {"cases": cases, "exact": exact, "accuracy": exact / cases,
            "mse": mse,
            "maximum_absolute_error": max(error for row in errors for error in row)}


def continuation_metrics(rows: list[dict], outputs_a: list[list[list[float]]],
                         outputs_b: list[list[list[float]]], current_a: list[list[float]],
                         current_b: list[list[float]], states_a: list[list[float]],
                         states_b: list[list[float]], tolerance: float = 0.25) -> dict[str, dict]:
    """Compare paired suffix correctness, agreement, and native-state distance."""
    tol = _tolerance(tolerance)
    _rows(rows, "rows")
    checked_a, targets_by_row = _trajectory_rows(rows, outputs_a, "outputs_a", "suffix")
    checked_b, _ = _trajectory_rows(rows, outputs_b, "outputs_b", "suffix")
    currents_a = _parallel_vectors(current_a, len(rows), "current_a")
    currents_b = _parallel_vectors(current_b, len(rows), "current_b")
    checked_states_a = _parallel_vectors(states_a, len(rows), "states_a")
    checked_states_b = _parallel_vectors(states_b, len(rows), "states_b")
    if not rows:
        return {}

    groups: dict[str, dict[str, Any]] = {}

    def group_for(key: str) -> dict[str, Any]:
        if key not in groups:
            groups[key] = {"cases": 0, "both_suffix_exact": 0, "both_suffix_accuracy": 0.0,
                           "current_both_exact": 0, "conditional_suffix_exact": 0,
                           "conditional_accuracy": None, "close_agreement": 0,
                           "wrong_close_agreement": 0, "steps": {}, "first_error_step": {},
                           "_conditional_cases": 0, "_state_squared_sum": 0.0,
                           "_state_coordinate_count": 0}
        return groups[key]

    for index, row in enumerate(rows):
        targets = targets_by_row[index]
        trajectory_a, trajectory_b = checked_a[index], checked_b[index]
        exact_a = [[_absolute_error(x, y, "continuation") <= tol for x, y in zip(target, output)]
                   for target, output in zip(targets, trajectory_a)]
        exact_b = [[_absolute_error(x, y, "continuation") <= tol for x, y in zip(target, output)]
                   for target, output in zip(targets, trajectory_b)]
        exact_steps = [all(left) and all(right) for left, right in zip(exact_a, exact_b)]
        suffix_exact = all(exact_steps)
        first_error = next((step for step, exact in enumerate(exact_steps, start=1) if not exact), None)
        current = _vector(row.get("current"), f"row {index} current")
        current_exact = (all(_absolute_error(x, y, "continuation current") <= tol for x, y in zip(current, currents_a[index]))
                         and all(_absolute_error(x, y, "continuation current") <= tol for x, y in zip(current, currents_b[index])))
        close = all(all(_absolute_error(x, y, "continuation agreement") <= tol for x, y in zip(left, right))
                    for left, right in zip(trajectory_a, trajectory_b))
        state_sq = [_square(_absolute_error(a, b, "state distance"), "state distance")
                    for a, b in zip(checked_states_a[index], checked_states_b[index])]
        keys = ("all", f"family/{row['family']}")
        for key in keys:
            group = group_for(key)
            group["cases"] += 1
            group["both_suffix_exact"] += int(suffix_exact)
            group["current_both_exact"] += int(current_exact)
            group["_conditional_cases"] += int(current_exact)
            group["conditional_suffix_exact"] = group.get("conditional_suffix_exact", 0) + int(current_exact and suffix_exact)
            group["close_agreement"] += int(close)
            group["wrong_close_agreement"] += int(close and not suffix_exact)
            error_key = "none" if first_error is None else str(first_error)
            group["first_error_step"][error_key] = group["first_error_step"].get(error_key, 0) + 1
            for step, exact in enumerate(exact_steps, start=1):
                one = group["steps"].setdefault(str(step), {"cases": 0, "both_exact": 0})
                one["cases"] += 1
                one["both_exact"] += int(exact)
            for value in state_sq:
                group["_state_squared_sum"] = _add_finite(group["_state_squared_sum"], value, "state distance")
            group["_state_coordinate_count"] += len(state_sq)

    result = {}
    for key, group in sorted(groups.items()):
        group["both_suffix_accuracy"] = group["both_suffix_exact"] / group["cases"]
        conditional_cases = group.pop("_conditional_cases")
        group["conditional_accuracy"] = (group["conditional_suffix_exact"] / conditional_cases
                                         if conditional_cases else None)
        group["first_error_step"] = dict(sorted(
            group["first_error_step"].items(),
            key=lambda item: (item[0] == "none", 0 if item[0] == "none" else int(item[0]))))
        group["steps"] = dict(sorted(group["steps"].items(), key=lambda item: int(item[0])))
        group["mean_squared_state_distance"] = (group.pop("_state_squared_sum")
                                                / group.pop("_state_coordinate_count"))
        if not math.isfinite(group["mean_squared_state_distance"]):
            _fail("state distance", "aggregate exceeds finite numeric range")
        result[key] = group
    return result


def _parallel_vectors(values: Any, length: int, where: str) -> list[list[float]]:
    if not isinstance(values, list) or len(values) != length:
        _fail(where, "case count differs from rows")
    return [_vector(value, f"{where} {index}") for index, value in enumerate(values)]
