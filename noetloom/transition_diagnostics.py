"""Post-hoc EXP-0006 diagnostics, separately registered as EXP-0007-D1."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

from .affine_model import fit_affine, forward_ops, rollout
from .calibration_records import publish_fit, write
from .contracts import ContractError, read_json
from .learning_worker import peak_rss_bytes
from .rollout_metrics import prefix_metrics
from .storage import file_digest, tree_bytes
from .transition_data import generate, transfer
from . import transition_worker as original_worker


def validate_registration(protocol: dict) -> None:
    keys = {"schema_version", "id", "kind", "historical_source_commit", "historical_evidence",
            "historical_evidence_sha256", "historical_protocol", "seeds", "snapshot_stages", "arm", "affine",
            "prefix_audit", "checkpoint_comparison", "backend", "budget", "verification", "claim_boundary",
            "network_during_run", "external_pretrained_components", "final_access", "retention"}
    if not isinstance(protocol, dict) or set(protocol) != keys:
        raise ContractError("diagnostic registration fields differ")
    if (protocol.get("schema_version") != "noetloom.transition_diagnostics.v1"
            or protocol.get("id") != "EXP-0007-D1" or protocol.get("kind") != "posthoc_development_diagnostics"
            or protocol.get("historical_source_commit") != "1eeda57e868fad0d3608c4f0cd30b93c0ba1e513"
            or protocol.get("historical_evidence") != "docs/evidence/N-008-2026-09-30.json"
            or protocol.get("historical_evidence_sha256") != "e33d465c25edbbf48a61fc22133eaf38f5645669d19cfefda760b997585d1806"
            or protocol.get("historical_protocol") != "experiments/EXP-0006/protocol.json"
            or protocol.get("seeds") != [9103, 9209, 9311] or protocol.get("snapshot_stages") != ["one", "mixed"]
            or protocol.get("arm") != "shared_transition" or protocol.get("final_access") is not False
            or protocol.get("network_during_run") is not False or protocol.get("external_pretrained_components") != []):
        raise ContractError("diagnostic registration identity or data boundary differs")
    expected = {"max_attempts": 4, "max_runs": 1, "max_replays": 3, "max_affine_fit_examples_per_run": 640,
                "max_scored_trajectories_per_run": 30000, "max_forward_prefixes_per_run": 20000,
                "max_output_bytes_per_run": 16777216, "max_wall_seconds_per_run": 120,
                "max_peak_rss_bytes": 2147483648, "max_artifact_bytes_total": 67108864,
                "max_wall_seconds_total": 480}
    if protocol.get("budget") != expected:
        raise ContractError("diagnostic numeric budget differs")
    if protocol.get("backend") != {"version": "2.14.0", "device": "cpu", "threads": 1,
                                   "neural_dtype": "float32", "affine_arithmetic": "Python float64"}:
        raise ContractError("diagnostic backend differs")
    if any(protocol["affine"].get(k) != v for k, v in {"training_examples": 640, "examples_per_action": 160,
                                                      "actions": 4, "width": 8}.items()):
        raise ContractError("diagnostic fitting scope differs")


def input_registry(evidence: dict) -> list[dict]:
    records = []
    for row in evidence["fit_records"]:
        selected = row["arm"] == "shared_transition" and row["stage"] in {"one", "mixed"}
        files = {"data": "data.json", "predictions": "predictions.json"}
        if selected:
            if row["condition"] != "lr003" or not row["acquisition"]["passed"]:
                raise ContractError("registered candidate checkpoint is not acquired")
            files["snapshot"] = "selected.json"
        records.append({"run": row["basename"], "kind": "fit", "arm": row["arm"], "seed": row["seed"],
                        "stage": row["stage"], "condition": row["condition"], "selected_step": row["selected_step"],
                        "manifest_sha256": row["manifest_sha256"], "files": files,
                        "snapshot_sha256": row["selected_snapshot_sha256"] if selected else None})
    for row in evidence["development_transfer"]:
        records.append({"run": row["run"], "kind": "transfer", "arm": "shared_transition", "seed": row["seed"],
                        "stage": "development_transfer", "condition": "lr003", "selected_step": 2048,
                        "manifest_sha256": row["manifest_sha256"],
                        "files": {"data": "transfer-data.json", "predictions": "transfer.json"}, "snapshot_sha256": None})
    if (len(records) != 27 or len({r["run"] for r in records}) != 27
            or sum(r["snapshot_sha256"] is not None for r in records) != 6):
        raise ContractError("diagnostic evidence input coverage differs")
    return records


def copied_name(index: int, role: str) -> str:
    return f"input-{index:02d}-{role}.json"


def load(path: Path):
    if path.stat().st_size > 2 * 1024**2:
        raise ContractError("diagnostic individual input exceeds admission")
    return json.loads(path.read_text())


def copy_bounded(source: Path, target: Path, directory: Path, limit: int) -> None:
    size = source.stat().st_size
    if size > 2 * 1024**2 or tree_bytes(directory, live=True) + size + 65536 > limit:
        raise ContractError("diagnostic original-byte copy exceeds output admission")
    payload = source.read_bytes()
    if len(payload) != size:
        raise ContractError("diagnostic input changed while copying")
    with target.open("xb") as handle:
        handle.write(payload)


def prepare_inputs(directory: Path, request: dict, protocol: dict, evidence: dict) -> list[dict]:
    records = input_registry(evidence)
    limit = protocol["budget"]["max_output_bytes_per_run"]
    root = Path(request["input_root"])
    replay = Path(request["original"]) if request["original"] else None
    for i, row in enumerate(records):
        sources = {"manifest": "manifest.json", **row["files"]}
        for role, name in sources.items():
            source = replay / copied_name(i, role) if replay else root / row["run"] / name
            copy_bounded(source, directory / copied_name(i, role), directory, limit)
    write(directory, "input-index.json", {"records": records})
    validate_inputs(directory, records, protocol, evidence)
    return records


def validate_inputs(directory: Path, records: list[dict], protocol: dict, evidence: dict) -> None:
    if records != input_registry(evidence):
        raise ContractError("diagnostic input registry differs")
    for i, row in enumerate(records):
        path = directory / copied_name(i, "manifest")
        if file_digest(path) != row["manifest_sha256"]:
            raise ContractError("historical diagnostic manifest differs")
        manifest = read_json(path)
        if (manifest["source_commit"] != protocol["historical_source_commit"] or manifest["status"] != "passed"
                or manifest["source"] != evidence["source"]):
            raise ContractError("historical diagnostic source or execution status differs")
        artifacts = {a["path"]: a for a in manifest["artifacts"]}
        for role, name in row["files"].items():
            copied = directory / copied_name(i, role)
            if copied.stat().st_size != artifacts[name]["bytes"] or file_digest(copied) != artifacts[name]["sha256"]:
                raise ContractError("historical diagnostic input bytes differ")
        if row["snapshot_sha256"] and file_digest(directory / copied_name(i, "snapshot")) != row["snapshot_sha256"]:
            raise ContractError("diagnostic selected snapshot differs")


def scored(rows: list[dict], logits: list, usage: dict) -> dict:
    usage["scored_trajectories"] += len(rows)
    usage["scored_prefixes"] += sum(len(row["actions"]) for row in rows)
    return prefix_metrics(rows, logits)


def audit_saved(directory: Path, records: list[dict], usage: dict) -> list[dict]:
    result = []
    for i, record in enumerate(records):
        data = load(directory / copied_name(i, "data"))
        saved = read_json(directory / copied_name(i, "predictions"))
        splits = ("training", "validation") if record["kind"] == "fit" else ("development",)
        row = {key: record[key] for key in ("run", "arm", "seed", "stage", "condition", "selected_step")}
        row["splits"] = {}
        for split in splits:
            examples = data[split] if record["kind"] == "fit" else data
            old = saved[split] if record["kind"] == "fit" else saved
            measured = scored(examples, old["logits"], usage)
            if set(measured) != set(old["scored"]):
                raise ContractError("prefix audit endpoint group support differs")
            for key, values in measured.items():
                if values["cases"] != old["scored"][key]["cases"] or values["final_exact"] != old["scored"][key]["exact"]:
                    raise ContractError("prefix audit does not reproduce historical endpoint metrics")
            if [[int(value >= 0) for value in logits[-1]] for logits in old["logits"]] != old["predictions"]:
                raise ContractError("historical saved endpoint bits differ from their logits")
            row["splits"][split] = measured
        result.append(row)
    return result


def compute(directory: Path, records: list[dict], history: dict, usage: dict, fit: dict) -> dict:
    engine = original_worker.backend(history)
    work = original_worker.Work()
    development = transfer(history, "development")
    if len(development) != 608:
        raise ContractError("diagnostic development case count differs")
    original_transfers = {}
    for i, row in enumerate(records):
        if row["kind"] == "transfer":
            if load(directory / copied_name(i, "data")) != development:
                raise ContractError("diagnostic generator does not match inspected development bytes")
            original_transfers[row["seed"]] = read_json(directory / copied_name(i, "predictions"))
    results = {"saved_prefix_audit": audit_saved(directory, records, usage), "neural": []}
    outputs = {"neural": []}
    for i, row in enumerate(records):
        if not row["snapshot_sha256"]:
            continue
        snapshot = read_json(directory / copied_name(i, "snapshot"))
        if (snapshot["seed"] != row["seed"] or snapshot["step"] != row["selected_step"]
                or snapshot["arm"] != "shared_transition"):
            raise ContractError("registered snapshot identity differs")
        model = engine.Model.restore(snapshot)
        value = original_worker.evaluate(engine, model, development, work)
        reference = original_worker.reference_check(engine, model, development, work)
        if row["stage"] == "mixed" and value != original_transfers[row["seed"]]:
            raise ContractError("new mixed checkpoint inference differs from retained transfer result")
        identity = {key: row[key] for key in ("run", "seed", "stage", "selected_step", "snapshot_sha256")}
        results["neural"].append({**identity, "endpoint": value["scored"],
                                  "prefix": scored(development, value["logits"], usage), "reference": reference})
        outputs["neural"].append({**identity, "outputs": value})
    affine_outputs = [rollout(fit["parameters"], [2.0 * bit - 1 for bit in row["initial"]], row["actions"])
                      for row in development]
    affine_steps = sum(len(row["actions"]) for row in development)
    usage.update(neural_forward=work.record(), affine_forward_prefixes=affine_steps,
                 affine_forward_ops=forward_ops(8, affine_steps))
    maximum = max(abs(value - (2 * truth - 1))
                  for row, trajectory in zip(development, affine_outputs)
                  for target, actual in zip(row["targets"], trajectory) for truth, value in zip(target, actual))
    results["affine"] = {"prefix": scored(development, affine_outputs, usage),
                         "maximum_absolute_bipolar_coordinate_error": maximum,
                         "fit_report": fit["report"],
                         "scope": "Continuous outputs thresholded only for scoring; fit and inference receive observed examples, never exact rules."}
    outputs["affine"] = affine_outputs
    write(directory, "outputs.json", outputs)
    write(directory, "result.json", results)
    return results


def main() -> None:
    directory = Path(sys.argv[1])
    protocol, request = read_json(directory / "protocol.json"), read_json(directory / "request.json")
    validate_registration(protocol)
    root = Path(request["source_root"])
    evidence_path = root / protocol["historical_evidence"]
    if file_digest(evidence_path) != protocol["historical_evidence_sha256"]:
        raise ContractError("historical evidence differs from diagnostic registration")
    evidence, history = read_json(evidence_path), read_json(root / protocol["historical_protocol"])
    records = prepare_inputs(directory, request, protocol, evidence)
    generated = generate(history, "one")["training"]
    # Compare to the exact original one-step training bytes before presenting examples.
    one = next(i for i, row in enumerate(records) if row["snapshot_sha256"] and row["stage"] == "one")
    if generated != read_json(directory / copied_name(one, "data"))["training"] or len(generated) != 640:
        raise ContractError("affine fitting data differs from the registered observations")
    examples = [{"input": [2.0 * bit - 1 for bit in row["initial"]], "action": row["actions"][0],
                 "target": [2.0 * bit - 1 for bit in row["targets"][0]]} for row in generated]
    started = time.monotonic()
    parameters, report = fit_affine(examples, actions=4)
    usage = {"gradient_updates": 0, "affine_fit_examples": len(examples), "scored_trajectories": 0,
             "scored_prefixes": 0}
    fit = {"schema_version": "noetloom.affine_diagnostic_fit.v1", "parameters": parameters, "report": report,
           "completed_updates": 0, "fitting_seconds": time.monotonic() - started,
           "fitting_scope": "Four deterministic full-batch affine solves; no neural optimization."}

    def verify():
        results = compute(directory, records, history, usage, fit)
        replay = None
        if request["original"]:
            original = Path(request["original"])
            if (results != read_json(original / "result.json")
                    or file_digest(directory / "outputs.json") != file_digest(original / "outputs.json")
                    or parameters != read_json(original / "fit.json")["parameters"]):
                raise ContractError("fresh diagnostic fit, outputs or metrics do not replay")
            replay = {"status": "passed", "original_manifest_sha256": request["original_manifest_sha256"],
                      "scope": "All prefix audits, six frozen neural snapshots and deterministic affine fitting/prediction recomputed."}
            write(directory, "replay.json", replay)
        limits = protocol["budget"]
        if (usage["scored_trajectories"] > limits["max_scored_trajectories_per_run"]
                or usage["affine_fit_examples"] > limits["max_affine_fit_examples_per_run"]
                or usage["neural_forward"]["prefix_predictions"] + usage["affine_forward_prefixes"] > limits["max_forward_prefixes_per_run"]):
            raise ContractError("diagnostic measured work exceeds registration")
        write(directory, "work.json", usage)
        write(directory, "worker-resources.json", {"peak_rss_bytes": peak_rss_bytes()})
        return {"prefix_audits": len(records), "neural_checkpoints": 6, "affine_examples": len(examples), "replay": replay}

    publish_fit(directory, fit, verify)


if __name__ == "__main__":
    main()
