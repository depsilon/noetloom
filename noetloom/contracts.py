"""Strict, versioned contracts and cross-document invariants.

These validators implement Noetloom's specific formats. They are not a general
JSON Schema engine, and structural validity does not establish scientific truth.
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

JSON_LIMIT = 2 * 1024 * 1024
CONTROLS = ("exact_memory", "no_memory", "stale_memory", "bounded_memory")
PHASES = ("initial", "delayed", "revision", "deletion", "unknown")
POLICY_FILES = {"local-small": "resource-policy.json", "ci-smoke": "resource-policy-ci.json",
                "local-calibration": "resource-policy-calibration.json"}


class ContractError(ValueError):
    """An input violates a declared contract; no execution should follow."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON property: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ContractError(f"non-finite JSON number: {value}")


def _float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ContractError("JSON number exceeds finite floating-point range")
    return parsed


def read_json(path: Path, max_bytes: int = JSON_LIMIT) -> dict[str, Any]:
    with path.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ContractError(f"JSON exceeds {max_bytes} bytes: {path.name}")
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ContractError(f"invalid JSON in {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be an object: {path.name}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def fields(value: Any, required: set[str], where: str, optional: set[str] | None = None) -> None:
    if not isinstance(value, dict):
        raise ContractError(f"{where} must be an object")
    missing = required - value.keys()
    extra = value.keys() - required - (optional or set())
    if missing or extra:
        raise ContractError(f"{where}: missing={sorted(missing)}, unknown={sorted(extra)}")


def text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{where} must be a nonempty string")
    return value


def integer(value: Any, where: str, low: int = 1, high: int | None = None) -> int:
    if type(value) is not int or value < low or (high is not None and value > high):
        raise ContractError(f"{where} must be an integer in [{low}, {high or 'unbounded'}]")
    return value


def strings(value: Any, where: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ContractError(f"{where} must be a {'possibly empty ' if allow_empty else ''}list")
    for item in value:
        text(item, where)
    if len(value) != len(set(value)):
        raise ContractError(f"{where} contains duplicates")
    return value


def version(value: dict[str, Any], expected: str) -> None:
    if value.get("schema_version") != expected:
        raise ContractError(f"expected schema_version={expected}")


def identifier(value: Any, pattern: str, where: str) -> str:
    text(value, where)
    if not re.fullmatch(pattern, value):
        raise ContractError(f"invalid {where}: {value}")
    return value


def validate_policy(policy: dict[str, Any]) -> None:
    numeric = {
        "max_workspace_bytes", "min_free_disk_bytes", "max_run_output_bytes",
        "max_wall_seconds", "max_cases", "max_memory_slots", "max_repo_file_bytes",
        "max_repo_total_bytes",
    }
    fields(policy, {"schema_version", "profile"} | numeric, "resource policy")
    version(policy, "noetloom.resources.v1")
    text(policy["profile"], "profile")
    for key in numeric:
        integer(policy[key], key)
    if policy["max_run_output_bytes"] > policy["max_workspace_bytes"]:
        raise ContractError("run output budget exceeds workspace budget")
    if policy["max_repo_file_bytes"] > policy["max_repo_total_bytes"]:
        raise ContractError("file budget exceeds repository budget")


def load_policy(root: Path, profile: str = "local-small") -> dict[str, Any]:
    if profile not in POLICY_FILES:
        raise ContractError(f"unknown resource profile: {profile}")
    policy = read_json(root / "config" / POLICY_FILES[profile])
    validate_policy(policy)
    if policy["profile"] != profile:
        raise ContractError("resource profile differs from its registered name")
    return policy


def query_count(protocol: dict[str, Any]) -> int:
    return len(protocol["seeds"]) * sum(
        split["episodes"] * (2 * split["memory_slots"] + split["updates"] + split["deletes"] + 1)
        for split in protocol["splits"]
    )


def validate_experiment(protocol: dict[str, Any], policy: dict[str, Any]) -> None:
    fields(protocol, {
        "schema_version", "id", "title", "kind", "hypothesis", "family", "source_refs",
        "controls", "seeds", "value_count", "bounded_memory_slots", "splits", "budget",
        "acceptance", "claim_boundary", "stop_conditions", "network_required",
        "pretrained_components", "training_performed",
    }, "experiment")
    version(protocol, "noetloom.experiment.v1")
    identifier(protocol["id"], r"EXP-\d{4}", "experiment id")
    for key in ("title", "hypothesis", "claim_boundary"):
        text(protocol[key], key)
    if protocol["kind"] != "harness_validation" or protocol["family"] != "mutable_recall_v1":
        raise ContractError("this runner admits only mutable_recall_v1 harness validation")
    if protocol["network_required"] is not False or protocol["training_performed"] is not False:
        raise ContractError("the bootstrap harness cannot request network access or training")
    if protocol["pretrained_components"] != []:
        raise ContractError("pretrained components are not admitted by this harness")
    strings(protocol["source_refs"], "source_refs")
    strings(protocol["stop_conditions"], "stop_conditions")
    controls = strings(protocol["controls"], "controls")
    if set(controls) != set(CONTROLS):
        raise ContractError(f"controls must contain exactly {CONTROLS}")
    seeds = protocol["seeds"]
    if not isinstance(seeds, list) or not 2 <= len(seeds) <= 16:
        raise ContractError("supply 2–16 independent seeds")
    for seed in seeds:
        integer(seed, "seed", 0, 2**32 - 1)
    if len(seeds) != len(set(seeds)):
        raise ContractError("duplicate seeds")
    integer(protocol["value_count"], "value_count", 2, 256)
    integer(protocol["bounded_memory_slots"], "bounded_memory_slots", 1, policy["max_memory_slots"])
    splits = protocol["splits"]
    if not isinstance(splits, list) or not 3 <= len(splits) <= 8:
        raise ContractError("supply 3–8 splits")
    names: set[str] = set()
    for split in splits:
        fields(split, {"name", "episodes", "memory_slots", "distractors", "updates", "deletes"}, "split")
        name = identifier(split["name"], r"[a-z][a-z0-9_]{0,39}", "split name")
        if name in names:
            raise ContractError(f"duplicate split: {name}")
        names.add(name)
        integer(split["episodes"], "episodes", 1, 1000)
        integer(split["memory_slots"], "memory_slots", 2, policy["max_memory_slots"])
        integer(split["distractors"], "distractors", 1, policy["max_memory_slots"])
        integer(split["updates"], "updates", 1, split["memory_slots"])
        integer(split["deletes"], "deletes", 1, split["memory_slots"])
        if split["updates"] + split["deletes"] > split["memory_slots"]:
            raise ContractError("updated and deleted key sets must be disjoint")
    if not {"development", "validation", "test"} <= names:
        raise ContractError("development, validation and test splits are required")
    if query_count(protocol) > policy["max_cases"]:
        raise ContractError("query count exceeds resource policy")
    budget = protocol["budget"]
    fields(budget, {"max_wall_seconds", "max_output_bytes"}, "budget")
    integer(budget["max_wall_seconds"], "max_wall_seconds", 1, policy["max_wall_seconds"])
    integer(budget["max_output_bytes"], "max_output_bytes", 1024, policy["max_run_output_bytes"])
    acceptance = protocol["acceptance"]
    fields(acceptance, {
        "exact_memory_accuracy", "negative_controls_must_fail", "require_disjoint_episode_inputs",
    }, "acceptance")
    if type(acceptance["exact_memory_accuracy"]) not in (int, float) or acceptance["exact_memory_accuracy"] != 1:
        raise ContractError("the exact reference must require 100% accuracy")
    negative = strings(acceptance["negative_controls_must_fail"], "negative controls")
    if set(negative) != set(CONTROLS) - {"exact_memory"}:
        raise ContractError("all three negative controls are required")
    if acceptance["require_disjoint_episode_inputs"] is not True:
        raise ContractError("input overlap detection must be enabled")


def validate_sources(catalog: dict[str, Any]) -> set[str]:
    fields(catalog, {"schema_version", "sources"}, "source catalog")
    version(catalog, "noetloom.sources.v1")
    if not isinstance(catalog["sources"], list) or not catalog["sources"]:
        raise ContractError("source catalog must be nonempty")
    ids: set[str] = set()
    for source in catalog["sources"]:
        fields(source, {
            "id", "title", "url", "year", "accessed_on", "review_depth", "mechanism",
            "supported_claim", "limitations", "license_note",
        }, "source")
        key = identifier(source["id"], r"R-[A-Z0-9]+(?:-[A-Z0-9]+)*", "source id")
        if key in ids:
            raise ContractError(f"duplicate source: {key}")
        ids.add(key)
        for field in ("title", "mechanism", "supported_claim", "license_note"):
            text(source[field], field)
        url = urlparse(text(source["url"], "url"))
        if url.scheme != "https" or not url.netloc:
            raise ContractError(f"{key}: source needs an absolute HTTPS URL")
        integer(source["year"], "year", 1900, 2200)
        try:
            dt.date.fromisoformat(text(source["accessed_on"], "accessed_on"))
        except ValueError as exc:
            raise ContractError(f"{key}: invalid access date") from exc
        if text(source["review_depth"], "review_depth") not in {"abstract", "paper", "documentation"}:
            raise ContractError(f"{key}: invalid review depth")
        strings(source["limitations"], "limitations")
    return ids


def repo_reference(root: Path, relative: str) -> Path:
    text(relative, "repository reference")
    path = Path(relative)
    target = (root / path).resolve()
    if path.is_absolute() or not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ContractError(f"missing or nonlocal repository reference: {relative}")
    return target


def validate_plan(plan: dict[str, Any], root: Path | None = None) -> None:
    fields(plan, {"schema_version", "items"}, "plan")
    version(plan, "noetloom.plan.v1")
    if not isinstance(plan["items"], list) or not plan["items"]:
        raise ContractError("plan must contain items")
    by_id: dict[str, Any] = {}
    active = 0
    for item in plan["items"]:
        fields(item, {
            "id", "title", "status", "depends_on", "sources", "outcome", "acceptance",
            "verification", "budget_profile", "stop_condition", "evidence",
        }, "plan item", {"blocker"})
        key = identifier(item["id"], r"N-\d{3}", "plan id")
        if key in by_id:
            raise ContractError(f"duplicate plan id: {key}")
        by_id[key] = item
        for field in ("title", "outcome", "budget_profile", "stop_condition"):
            text(item[field], field)
        for field in ("sources", "acceptance", "verification"):
            strings(item[field], field)
        strings(item["depends_on"], "depends_on", allow_empty=True)
        strings(item["evidence"], "evidence", allow_empty=True)
        if text(item["status"], "plan status") not in {"planned", "active", "blocked", "completed"}:
            raise ContractError(f"{key}: unknown status")
        active += item["status"] == "active"
        if item["status"] == "completed" and not item["evidence"]:
            raise ContractError(f"{key}: completed work needs evidence")
        if item["status"] == "blocked":
            text(item.get("blocker"), f"{key}.blocker")
        if root:
            for ref in item["sources"] + item["evidence"]:
                repo_reference(root, ref)
    if active > 1:
        raise ContractError("more than one primary work item is active")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            raise ContractError(f"cyclic plan dependency at {key}")
        if key in visited:
            return
        visiting.add(key)
        for dep in by_id[key]["depends_on"]:
            if dep not in by_id:
                raise ContractError(f"{key}: missing dependency {dep}")
            if by_id[key]["status"] in {"active", "completed"} and by_id[dep]["status"] != "completed":
                raise ContractError(f"{key}: unfinished dependency {dep}")
            visit(dep)
        visiting.remove(key)
        visited.add(key)

    for key in by_id:
        visit(key)


def next_item(plan: dict[str, Any]) -> dict[str, Any] | None:
    validate_plan(plan)
    completed = {item["id"] for item in plan["items"] if item["status"] == "completed"}
    active = [item for item in plan["items"] if item["status"] == "active"]
    if active:
        return active[0]
    return next((item for item in plan["items"] if item["status"] == "planned"
                 and set(item["depends_on"]) <= completed), None)


def validate_hypotheses(data: dict[str, Any], source_ids: set[str]) -> None:
    fields(data, {"schema_version", "hypotheses"}, "hypotheses")
    version(data, "noetloom.hypotheses.v2")
    if not isinstance(data["hypotheses"], list) or not data["hypotheses"]:
        raise ContractError("hypotheses must be nonempty")
    ids: set[str] = set()
    for row in data["hypotheses"]:
        fields(row, {
            "id", "category", "title", "status", "mechanism", "prediction", "falsifier",
            "source_refs", "novelty_status", "evidence",
        }, "hypothesis", {"question"})
        key = identifier(row["id"], r"H-\d{3}", "hypothesis id")
        if key in ids:
            raise ContractError(f"duplicate hypothesis: {key}")
        ids.add(key)
        for field in ("title", "mechanism", "prediction", "falsifier"):
            text(row[field], field)
        if row["category"] not in {"mechanism", "foundational_representation"}:
            raise ContractError(f"{key}: invalid hypothesis category")
        horizon = row["status"] == "horizon"
        if horizon:
            if row["category"] != "foundational_representation":
                raise ContractError(f"{key}: horizon is reserved for foundational representation questions")
            text(row.get("question"), "horizon question")
            if row["evidence"]:
                raise ContractError(f"{key}: promote a horizon question before recording experiment evidence")
        elif "question" in row:
            text(row["question"], "research question")
        refs = strings(row["source_refs"], "hypothesis sources", allow_empty=horizon)
        if not set(refs) <= source_ids:
            raise ContractError(f"{key}: unknown research source")
        if text(row["status"], "hypothesis status") not in {"horizon", "proposed", "testing", "supported_in_scope", "rejected"}:
            raise ContractError(f"{key}: invalid hypothesis status")
        if row["novelty_status"] != "unassessed":
            raise ContractError("novelty needs an explicit future review contract")
        evidence = strings(row["evidence"], "hypothesis evidence", allow_empty=True)
        if row["status"] in {"supported_in_scope", "rejected"} and not evidence:
            raise ContractError(f"{key}: a research conclusion needs evidence")


def repository_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        capture_output=True, check=True, timeout=10,
    )
    return sorted({root / name.decode("utf-8") for name in result.stdout.split(b"\0") if name})


def check_repository(root: Path) -> dict[str, Any]:
    policy = load_policy(root)
    profiles = {name: load_policy(root, name) for name in POLICY_FILES}
    plan = read_json(root / "docs/state/plan.json")
    validate_plan(plan, root)
    if any(item["budget_profile"] not in profiles for item in plan["items"]):
        raise ContractError("plan references an undefined resource profile")
    source_ids = validate_sources(read_json(root / "docs/research/sources.json"))
    hypotheses = read_json(root / "docs/research/hypotheses.json")
    validate_hypotheses(hypotheses, source_ids)
    for hypothesis in hypotheses["hypotheses"]:
        for ref in hypothesis["evidence"]:
            repo_reference(root, ref)
    protocols = list((root / "experiments").glob("*/protocol.json"))
    if not protocols:
        raise ContractError("no experiment protocol found")
    ids: set[str] = set()
    for path in protocols:
        protocol = read_json(path)
        if protocol.get("schema_version") == "noetloom.learning.v1":
            from .learning_contracts import validate_learning_protocol
            validate_learning_protocol(protocol, policy)
            repo_reference(root, protocol["design"])
        elif protocol.get("schema_version") == "noetloom.allocation.v1":
            from .allocation_contracts import validate_allocation_protocol
            validate_allocation_protocol(protocol, policy)
            repo_reference(root, protocol["design"])
            repo_reference(root, protocol["parents"])
        elif protocol.get("schema_version") == "noetloom.representation.v1":
            from .representation_contracts import validate_representation_protocol
            validate_representation_protocol(protocol, policy)
            repo_reference(root, protocol["design"])
        elif protocol.get("schema_version") == "noetloom.calibration.v1":
            from .calibration_contracts import validate_calibration_protocol
            validate_calibration_protocol(protocol, profiles["local-calibration"])
            repo_reference(root, protocol["design"])
            confirmation = path.parent / "confirmation.json"
            if confirmation.is_file():
                from .calibration_contracts import validate_confirmation
                validate_confirmation(read_json(confirmation))
        elif protocol.get("schema_version") == "noetloom.transitions.v1":
            from .transition_contracts import validate_protocol
            validate_protocol(protocol, profiles["local-calibration"])
            repo_reference(root, protocol["design"])
        else:
            validate_experiment(protocol, policy)
        if protocol["id"] in ids or path.parent.name != protocol["id"]:
            raise ContractError("protocol id duplicated or different from directory name")
        ids.add(protocol["id"])
        if not set(protocol["source_refs"]) <= source_ids:
            raise ContractError(f"{protocol['id']}: unresolved research references")
    total = 0
    files = repository_files(root)
    links = 0
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise ContractError(f"repository entry is not an ordinary file: {path.relative_to(root)}")
        size = path.stat().st_size
        total += size
        if size > policy["max_repo_file_bytes"]:
            raise ContractError(f"repository file budget exceeded: {path.relative_to(root)}")
        if path.suffix.lower() in {".pt", ".pth", ".ckpt", ".safetensors", ".npy", ".npz"}:
            raise ContractError(f"bulk learned/data artifact belongs outside Git: {path.name}")
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if path.suffix == ".md":
            content = re.sub(r"(?ms)^```.*?^```[^\n]*", "", path.read_text(encoding="utf-8"))
            for raw in re.findall(r"\[[^\]\n]*\]\(([^)\n]+)\)", content):
                target = raw.strip().strip("<>")
                if urlparse(target).scheme or target.startswith("#"):
                    continue
                target = unquote(target.split("#", 1)[0])
                resolved = (path.parent / target).resolve()
                if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
                    raise ContractError(f"broken local link in {path.relative_to(root)}: {target}")
                links += 1
    if total > policy["max_repo_total_bytes"]:
        raise ContractError("repository working-file budget exceeded")
    return {
        "status": "passed", "files_checked": len(files), "working_file_bytes": total,
        "local_links_checked": links, "protocols_checked": len(protocols),
        "sources_checked": len(source_ids), "hypotheses_checked": len(hypotheses["hypotheses"]),
        "proof_scope": "contract structure, cross-references, Python syntax, and working-file budgets",
    }
