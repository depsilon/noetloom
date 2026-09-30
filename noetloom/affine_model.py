"""Observed-example affine identification; no world or exact-transition access."""
from __future__ import annotations

import math

from .contracts import ContractError


def vector(values, width: int | None = None) -> list[float]:
    if not isinstance(values, list) or not values or (width is not None and len(values) != width):
        raise ContractError("affine vector has invalid shape")
    try:
        finite = all(type(value) in (int, float) and math.isfinite(value) for value in values)
    except (OverflowError, ValueError):
        finite = False
    if not finite:
        raise ContractError("affine vector contains a nonfinite or nonnumeric value")
    return [float(value) for value in values]


def solve(matrix: list[list[float]], rhs: list[list[float]]) -> tuple[list[list[float]], dict]:
    """Full-rank small-system Gauss-Jordan solve with partial pivoting.

    This diagnostic uses well-conditioned bipolar examples, not a general least-squares
    library replacement. Rank-deficient normal equations fail instead of choosing an
    unregistered regularizer or silently returning an arbitrary solution.
    """
    size = len(matrix)
    if not 1 <= size <= 33 or len(rhs) != size:
        raise ContractError("affine solve dimensions are outside admission")
    output = len(vector(rhs[0]))
    augmented = [vector(row, size) + vector(target, output) for row, target in zip(matrix, rhs)]
    magnitude = max(abs(value) for row in matrix for value in row)
    if not magnitude:
        raise ContractError("affine design is rank deficient")
    tolerance = 1e-12 * magnitude
    work = {"multiply": 0, "add": 0, "divide": 0, "pivot_comparisons": 0}
    pivots = []
    for col in range(size):
        pivot = max(range(col, size), key=lambda row: abs(augmented[row][col]))
        work["pivot_comparisons"] += size - col - 1
        value = augmented[pivot][col]
        if abs(value) <= tolerance:
            raise ContractError("affine design is numerically rank deficient")
        pivots.append(abs(value))
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        augmented[col] = [item / value for item in augmented[col]]
        work["divide"] += size + output
        for row in range(size):
            if row == col:
                continue
            factor = augmented[row][col]
            augmented[row] = [a - factor * b for a, b in zip(augmented[row], augmented[col])]
            work["multiply"] += size + output
            work["add"] += size + output
    result = [row[size:] for row in augmented]
    if any(not math.isfinite(value) for row in result for value in row):
        raise ContractError("affine solve produced nonfinite parameters")
    return result, {"rank": size, "absolute_pivots": pivots, "work": work,
                    "scope": "Normal equations, partial pivoting, float64 arithmetic; pivot spread is not a condition number."}


def fit_affine(examples: list[dict], *, actions: int) -> tuple[dict, dict]:
    """Fit action-specific affine maps from only (input, action, target) examples."""
    if not isinstance(examples, list) or not examples or len(examples) > 10000 or type(actions) is not int or not 1 <= actions <= 16:
        raise ContractError("affine fitting data is outside admission")
    if not isinstance(examples[0], dict) or set(examples[0]) != {"input", "action", "target"}:
        raise ContractError("affine learner accepts only observed input, action and target")
    width = len(vector(examples[0]["input"]))
    if width > 32:
        raise ContractError("affine state width exceeds admission")
    buckets = [[] for _ in range(actions)]
    for row in examples:
        if not isinstance(row, dict) or set(row) != {"input", "action", "target"}:
            raise ContractError("affine learner accepts only observed input, action and target")
        action = row["action"]
        if type(action) is not int or not 0 <= action < actions:
            raise ContractError("affine action is invalid")
        buckets[action].append((vector(row["input"], width) + [1.0], vector(row["target"], width)))
    models, reports = [], []
    for rows in buckets:
        size = width + 1
        if len(rows) < size:
            raise ContractError("affine action has insufficient observations")
        gram = [[sum(x[i] * x[j] for x, _ in rows) for j in range(size)] for i in range(size)]
        cross = [[sum(x[i] * y[j] for x, y in rows) for j in range(width)] for i in range(size)]
        coefficients, report = solve(gram, cross)
        coefficients = [list(column) for column in zip(*coefficients)]
        models.append({"weight": [row[:-1] for row in coefficients], "bias": [row[-1] for row in coefficients]})
        report.update(examples=len(rows), normal_equation_multiply=len(rows) * size * (size + width),
                      normal_equation_add=len(rows) * size * (size + width))
        reports.append(report)
    parameters = {"schema_version": "noetloom.affine_parameters.v1", "width": width, "actions": models}
    validate_parameters(parameters)
    return parameters, {"examples": len(examples), "parameter_count": actions * width * (width + 1),
                        "actions": reports, "gradient_updates": 0,
                        "input_contract": "Only observed input/action/target tuples; no world configuration, masks, permutations or inverse observation mapping."}


def validate_parameters(parameters: dict) -> None:
    if not isinstance(parameters, dict) or set(parameters) != {"schema_version", "width", "actions"}:
        raise ContractError("affine parameter fields differ")
    width = parameters["width"]
    if parameters["schema_version"] != "noetloom.affine_parameters.v1" or type(width) is not int or not 1 <= width <= 32:
        raise ContractError("affine parameter schema or width differs")
    if not isinstance(parameters["actions"], list) or not 1 <= len(parameters["actions"]) <= 16:
        raise ContractError("affine action bank differs")
    for row in parameters["actions"]:
        if (not isinstance(row, dict) or set(row) != {"weight", "bias"}
                or not isinstance(row["weight"], list) or len(row["weight"]) != width):
            raise ContractError("affine action parameters differ")
        vector(row["bias"], width)
        for weights in row["weight"]:
            vector(weights, width)


def rollout(parameters: dict, initial: list[float], actions: list[int]) -> list[list[float]]:
    """Evolve continuous predictions without rounding or intermediate observations."""
    validate_parameters(parameters)
    state = vector(initial, parameters["width"])
    if not isinstance(actions, list) or any(type(a) is not int or not 0 <= a < len(parameters["actions"]) for a in actions):
        raise ContractError("affine rollout actions differ")
    outputs = []
    for action in actions:
        model = parameters["actions"][action]
        state = [sum(w * x for w, x in zip(weights, state)) + bias for weights, bias in zip(model["weight"], model["bias"])]
        state = vector(state, parameters["width"])
        outputs.append(state)
    return outputs


def forward_ops(width: int, steps: int) -> dict:
    return {"multiply": steps * width * width, "add": steps * (width * width + width)}
