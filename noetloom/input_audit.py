"""Finite input-equivalence diagnostics; no learner, task decoder or training imports."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Hashable
from itertools import combinations

from .contracts import ContractError, canonical_bytes


def audit_inputs(groups: dict[str, list[dict]], signature: Callable[[dict], Hashable]) -> dict:
    """Count known equivalent observations and conflicting targets, retaining multiplicity.

    The caller owns the signature's connection to actual fixed preprocessing or a
    documented architectural symmetry. Absence of a collision is a finite check,
    not proof of general observability, learnability, or structural novelty.
    """
    if not groups or any(not name or not rows for name, rows in groups.items()):
        raise ContractError("input audit requires named, nonempty groups")
    signatures, labels, split_counts = {}, {}, {}
    for name, rows in groups.items():
        counts = Counter()
        for row in rows:
            key = signature(row)
            counts[key] += 1
            labels.setdefault(key, set()).add(canonical_bytes(row["expected"]))
        signatures[name] = counts
        split_counts[name] = {"cases": len(rows), "distinct_signatures": len(counts)}
    conflicts = {key for key, targets in labels.items() if len(targets) > 1}
    for name, counts in signatures.items():
        split_counts[name]["conflicting_cases"] = sum(count for key, count in counts.items() if key in conflicts)
    overlap = {}
    for left, right in combinations(groups, 2):
        shared = signatures[left].keys() & signatures[right].keys()
        overlap[f"{left}/{right}"] = {
            "distinct_signatures": len(shared),
            "left_cases": sum(signatures[left][key] for key in shared),
            "right_cases": sum(signatures[right][key] for key in shared),
        }
    return {"groups": split_counts, "conflicting_signatures": len(conflicts), "overlap": overlap}


def require_informative_inputs(report: dict, *, disjoint_pairs: tuple[str, ...] = ()) -> None:
    """Reject known ambiguity, and require separation for explicitly claimed holdouts.

    Optimization calibration can permit disclosed same-target overlap by omitting
    the pair. A transfer claim must declare its pairs and applicable signatures.
    """
    if report["conflicting_signatures"]:
        raise ContractError("different targets share a model input equivalence class")
    for pair in disjoint_pairs:
        if pair not in report["overlap"]:
            raise ContractError(f"input audit omits required partition pair: {pair}")
        if report["overlap"][pair]["distinct_signatures"]:
            raise ContractError(f"model-equivalent observations cross held-out partitions: {pair}")
