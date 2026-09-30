"""Bounded affine least-squares identification inside a ten-dimensional latent space."""
from __future__ import annotations

import math
import numbers

import torch

from noetloom.contracts import ContractError


def solve_affine(initial: torch.Tensor, target: torch.Tensor, *, rcond: float = 1e-10,
                 max_condition: float = 1e8) -> tuple[torch.Tensor, torch.Tensor, dict[str, object]]:
    """Fit ``target ~= initial @ weight.T + bias`` with a full-rank affine solve.

    Inputs are CPU float64 ``N x 10`` tensors with at least eleven rows. The
    returned weight and bias are float32; ill-conditioned or nonstationary fits
    are rejected explicitly rather than regularized or replaced by a fallback.
    """
    if (isinstance(rcond, bool) or not isinstance(rcond, numbers.Real)
            or isinstance(max_condition, bool) or not isinstance(max_condition, numbers.Real)):
        raise ContractError("rcond and max_condition must be finite numbers")
    rcond_value = float(rcond)
    condition_limit = float(max_condition)
    if not math.isfinite(rcond_value) or not 0 < rcond_value < 1:
        raise ContractError("rcond must be finite and in (0, 1)")
    if not math.isfinite(condition_limit) or condition_limit < 1:
        raise ContractError("max_condition must be finite and at least 1")
    if not torch.is_tensor(initial) or not torch.is_tensor(target):
        raise ContractError("initial and target must be torch tensors")
    if initial.device.type != "cpu" or target.device.type != "cpu":
        raise ContractError("initial and target must be on CPU")
    if initial.dtype != torch.float64 or target.dtype != torch.float64:
        raise ContractError("initial and target must have dtype torch.float64")
    if initial.ndim != 2 or initial.shape[1] != 10:
        raise ContractError("initial must have shape N x 10")
    if target.ndim != 2 or target.shape != initial.shape:
        raise ContractError("target must match initial shape N x 10")
    if initial.shape[0] < 11:
        raise ContractError("affine solve requires at least 11 rows")
    if not bool(torch.isfinite(initial).all()) or not bool(torch.isfinite(target).all()):
        raise ContractError("initial and target must contain only finite values")

    with torch.no_grad():
        design = torch.cat((initial, torch.ones((initial.shape[0], 1), dtype=torch.float64)), dim=1)
        try:
            result = torch.linalg.lstsq(design, target, rcond=rcond_value, driver="gelsd")
        except (RuntimeError, TypeError, ValueError) as exc:
            raise ContractError(f"affine least-squares solve failed: {exc}") from exc
        rank = int(result.rank.item())
        singular = result.singular_values
        if rank != 11 or singular.numel() != 11:
            raise ContractError("affine design must have rank 11 and 11 singular values")
        singular_values = singular.tolist()
        if (not all(math.isfinite(value) and value > 0 for value in singular_values)):
            raise ContractError("affine design singular values must be finite and positive")
        condition = singular_values[0] / singular_values[-1]
        if not math.isfinite(condition) or condition > condition_limit:
            raise ContractError("affine design exceeds max_condition")

        solution = result.solution
        if not bool(torch.isfinite(solution).all()):
            raise ContractError("affine solution must be finite")
        residual = design @ solution - target
        latent_mse_float64 = float(residual.square().mean().item())
        normal_residual = design.T @ residual
        denominator = (torch.linalg.vector_norm(design) * torch.linalg.vector_norm(target)
                       + torch.finfo(torch.float64).tiny)
        normal_residual_ratio = float((torch.linalg.vector_norm(normal_residual) / denominator).item())
        if not math.isfinite(normal_residual_ratio) or normal_residual_ratio > 1e-10:
            raise ContractError("affine solution fails the normal-residual stationarity check")

        weight = solution[:10].T.contiguous().to(dtype=torch.float32)
        bias = solution[10].contiguous().to(dtype=torch.float32)
        if not bool(torch.isfinite(weight).all()) or not bool(torch.isfinite(bias).all()):
            raise ContractError("affine coefficients must remain finite after float32 cast")
        cast_prediction = initial @ weight.to(dtype=torch.float64).T + bias.to(dtype=torch.float64)
        latent_mse_float32 = float((cast_prediction - target).square().mean().item())
        if not math.isfinite(latent_mse_float64) or not math.isfinite(latent_mse_float32):
            raise ContractError("affine fit residuals must be finite")

    diagnostic: dict[str, object] = {
        "rows": int(initial.shape[0]),
        "rank": rank,
        "singular_values": singular_values,
        "condition": condition,
        "latent_mse_float64": latent_mse_float64,
        "latent_mse_float32": latent_mse_float32,
        "normal_residual_ratio": normal_residual_ratio,
    }
    return weight, bias, diagnostic
