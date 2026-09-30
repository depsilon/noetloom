#!/usr/bin/env python3
"""Reproduce the retrospective EXP-0005 input-validity audit, without learning."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from noetloom.calibration_data import SURFACES, orbit_key, partitions, render, rows
from noetloom.contracts import ContractError, read_json
from noetloom.input_audit import audit_inputs, require_informative_inputs

SOURCES = ("noetloom/calibration_data.py", "noetloom/calibration_model.py", "noetloom/calibration_torch.py",
           "experiments/EXP-0005/protocol.json", "experiments/EXP-0005/confirmation.json",
           "docs/evidence/N-007-2026-09-30.json", "noetloom/input_audit.py", "scripts/audit_calibration_inputs.py")


def full_field(case: dict) -> tuple:
    return tuple(case["values"])


def consumed_rows(case: dict) -> tuple:
    # EXP-0005 shared_rows: fixed first-six-row slice, followed by shared phi and sum.
    # Sorting is an audit signature only. It is never fed to the learned model.
    return tuple(sorted(tuple(case["values"][offset:offset + 8]) for offset in range(0, 48, 8)))


def audit() -> dict:
    protocol = read_json(ROOT / "experiments/EXP-0005/protocol.json")
    split = partitions(protocol["data"])
    report = {"schema_version": "noetloom.input_validity_audit.v1", "experiment": "EXP-0005",
              "mode": "retrospective; inspected final partition is already retired",
              "model": "shared_rows", "preprocessing": "first 48 values as six rows; shared row encoder and sum",
              "equivalence_scope": "Row multiset is an architectural symmetry in exact arithmetic; floating reduction order may differ. No learned weights or scores are used to form signatures.",
              "query_reversal": {}, "partition_audit": {}, "historical_scores_by_format": []}
    for surface in SURFACES:
        opposite = [rows([(tuple(range(6)), query)], (surface,), "transpose")[0]
                    for query in ((0, 5), (5, 0))]
        a, b = opposite
        report["query_reversal"][surface] = {
            "order": list(range(6)), "queries": [[0, 5], [5, 0]],
            "labels": [a["expected"], b["expected"]],
            "full_field_differing_indices": [i for i, (x, y) in enumerate(zip(a["values"], b["values"])) if x != y],
            "consumed_values_equal": a["values"][:48] == b["values"][:48],
            "full_field": audit_inputs({"opposite_queries": opposite}, full_field),
            "shared_rows": audit_inputs({"opposite_queries": opposite}, consumed_rows),
        }
        groups = {name: rows(split[name], (surface,)) for name in ("training", "validation", "confirmation")}
        report["partition_audit"][surface] = {
            "exact_observation": audit_inputs(groups, full_field),
            "latent_orbit": audit_inputs(groups, lambda case: orbit_key(*map(tuple, case["latent"]))),
            "shared_rows": audit_inputs(groups, consumed_rows),
        }
    historical = read_json(ROOT / "docs/evidence/N-007-2026-09-30.json")
    for fit in historical["confirmation"]["fits"]:
        scored = fit["trained_final"]
        report["historical_scores_by_format"].append({
            "seed": fit["seed"], "acquired": fit["acquisition"]["passed"],
            "canonical": None if scored is None else {surface: scored["identity/" + surface] for surface in SURFACES},
            "row_permutation": None if scored is None else {surface: scored["row_permutation/" + surface] for surface in SURFACES},
        })
    # The rank/sequence domain has six possible marked ranks for the first query
    # entity and five for the second: all 30 patterns already occur in training.
    report["effective_domain"] = {}
    for surface in ("ranks", "sequence"):
        patterns = {consumed_rows({"values": render(tuple(range(6)), query, surface)})
                    for query in itertools.permutations(range(6), 2)}
        report["effective_domain"][surface] = {"query_rank_pairs": 6 * 5, "distinct_signatures": len(patterns)}
    report["scope"] = "Deterministic task/input audit and re-tabulation of previously published scores; no fitting, checkpoint access, new model evaluation or claim of general structural separation."
    report["source_files"] = [{"path": path, "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
                              for path in SOURCES]
    report["historical_result_revision"] = "9ceafecd9bd2a3935a329f02d192ef4842367965"
    return report


def require_transfer_admission(report: dict) -> None:
    for surface in SURFACES:
        require_informative_inputs(report["query_reversal"][surface]["shared_rows"])
        require_informative_inputs(report["partition_audit"][surface]["shared_rows"],
                                   disjoint_pairs=("training/validation", "training/confirmation"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-transfer", action="store_true", help="exit nonzero if this historical configuration is inadmissible for the claimed transfer")
    args = parser.parse_args()
    report = audit()
    try:
        require_transfer_admission(report)
        report["transfer_admission"] = {"passed": True}
    except ContractError as error:
        report["transfer_admission"] = {"passed": False, "reason": str(error)}
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(args.require_transfer and not report["transfer_admission"]["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
