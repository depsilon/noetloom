from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, plan_fixture, policy, protocol
from noetloom.contracts import (ContractError, load_policy, next_item, query_count, read_json, repo_reference,
                                validate_experiment, validate_hypotheses, validate_plan,
                                validate_policy, validate_sources)


class ContractTests(unittest.TestCase):
    def test_registered_protocol_and_workload(self):
        validate_policy(policy())
        validate_experiment(protocol(), policy())
        self.assertEqual(query_count(protocol()), 3024)

    def test_json_ambiguity_nonfinite_and_size_are_refused(self):
        with tempfile.TemporaryDirectory() as location:
            path = Path(location) / "data.json"
            for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}',
                        b'{"x":1e999}', b'[]', b'\xff', b'{broken', b'{"x":' + b'9' * 5000 + b'}'):
                with self.subTest(raw=raw):
                    path.write_bytes(raw)
                    with self.assertRaises(ContractError):
                        read_json(path)
            path.write_text('{"ok":1}')
            with self.assertRaisesRegex(ContractError, "exceeds"):
                read_json(path, max_bytes=4)

    def test_rejects_unknown_version_fields_and_hidden_execution(self):
        for key, value in (("schema_version", "noetloom.experiment.v99"), ("typo", 1),
                           ("training_performed", True), ("network_required", True),
                           ("pretrained_components", ["hidden-verifier"]), ("kind", "training")):
            with self.subTest(key=key):
                changed = protocol()
                changed[key] = value
                with self.assertRaises(ContractError):
                    validate_experiment(changed, policy())

    def test_protocol_requires_controls_independent_seeds_and_splits(self):
        changes = [
            ("controls", ["exact_memory"]), ("seeds", [True, 2]),
            ("seeds", [11, 11]), ("seeds", [11]), ("value_count", 1),
            ("bounded_memory_slots", 0), ("splits", protocol()["splits"][:2]),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                changed = protocol()
                changed[key] = value
                with self.assertRaises(ContractError):
                    validate_experiment(changed, policy())
        changed = protocol()
        changed["splits"][1]["name"] = "development"
        with self.assertRaisesRegex(ContractError, "duplicate split"):
            validate_experiment(changed, policy())

    def test_protocol_refuses_budget_bypass(self):
        for key, value in (("max_wall_seconds", 121), ("max_output_bytes", 67108865)):
            changed = protocol()
            changed["budget"][key] = value
            with self.assertRaises(ContractError):
                validate_experiment(changed, policy())
        changed = protocol()
        changed["splits"][0]["episodes"] = 1000
        with self.assertRaisesRegex(ContractError, "query count"):
            validate_experiment(changed, policy())
        changed = protocol()
        changed["splits"][0]["updates"] = 4
        with self.assertRaisesRegex(ContractError, "disjoint"):
            validate_experiment(changed, policy())

    def test_acceptance_cannot_disable_checks(self):
        for key, value in (("exact_memory_accuracy", True), ("exact_memory_accuracy", 0.9),
                           ("negative_controls_must_fail", ["no_memory"]),
                           ("require_disjoint_episode_inputs", False)):
            changed = protocol()
            changed["acceptance"][key] = value
            with self.assertRaises(ContractError):
                validate_experiment(changed, policy())

    def test_policy_consistency_and_strict_types(self):
        for key, value in (("max_workspace_bytes", 1), ("max_repo_total_bytes", 1),
                           ("min_free_disk_bytes", True), ("max_wall_seconds", 0)):
            changed = policy()
            changed[key] = value
            with self.assertRaises(ContractError):
                validate_policy(changed)

    def test_queue_selection_dependencies_and_completion_evidence(self):
        plan = plan_fixture()
        self.assertEqual(next_item(plan)["id"], "N-001")
        plan["items"][0]["status"] = "completed"
        with self.assertRaisesRegex(ContractError, "evidence"):
            validate_plan(plan)
        plan["items"][0]["evidence"] = ["record.json"]
        self.assertEqual(next_item(plan)["id"], "N-002")
        plan["items"][1]["status"] = "blocked"
        with self.assertRaises(ContractError):
            validate_plan(plan)
        plan["items"][1]["blocker"] = "missing prerequisite"
        self.assertIsNone(next_item(plan))

    def test_profiles_are_explicit_and_preserve_local_default(self):
        local = load_policy(ROOT)
        ci = load_policy(ROOT, "ci-smoke")
        self.assertEqual(local["min_free_disk_bytes"], 20 * 1024**3)
        self.assertEqual(ci["min_free_disk_bytes"], 512 * 1024**2)
        validate_experiment(protocol(), ci)
        with self.assertRaisesRegex(ContractError, "unknown resource profile"):
            load_policy(ROOT, "unlimited")

    def test_plan_refuses_cycles_missing_dependencies_and_concurrent_items(self):
        original = plan_fixture()
        for mutation in ("cycle", "missing", "active-dependency", "multiple-active"):
            with self.subTest(mutation=mutation):
                plan = copy.deepcopy(original)
                if mutation == "cycle":
                    plan["items"][0]["depends_on"] = ["N-003"]
                elif mutation == "missing":
                    plan["items"][0]["depends_on"] = ["N-999"]
                elif mutation == "active-dependency":
                    plan["items"][1]["status"] = "active"
                else:
                    for item in plan["items"][:2]:
                        item["status"] = "active"
                        item["depends_on"] = []
                with self.assertRaises(ContractError):
                    validate_plan(plan)

    def test_references_cannot_escape_or_silently_disappear(self):
        with tempfile.TemporaryDirectory() as location:
            parent = Path(location)
            root = parent / "repo"
            root.mkdir()
            (parent / "outside.md").write_text("outside")
            (root / "inside.md").write_text("inside")
            self.assertEqual(repo_reference(root, "inside.md"), (root / "inside.md").resolve())
            for ref in ("missing.md", "../outside.md", str(parent / "outside.md")):
                with self.assertRaises(ContractError):
                    repo_reference(root, ref)

    def test_research_provenance_and_conclusions_need_evidence(self):
        sources = read_json(ROOT / "docs/research/sources.json")
        ids = validate_sources(sources)
        hypotheses = read_json(ROOT / "docs/research/hypotheses.json")
        validate_hypotheses(hypotheses, ids)
        hypotheses["hypotheses"][0]["status"] = "supported_in_scope"
        with self.assertRaisesRegex(ContractError, "evidence"):
            validate_hypotheses(hypotheses, ids)
        hypotheses["hypotheses"][0]["status"] = "proposed"
        hypotheses["hypotheses"][0]["source_refs"] = ["R-INVENTED"]
        with self.assertRaisesRegex(ContractError, "unknown research source"):
            validate_hypotheses(hypotheses, ids)
        sources["sources"].append(copy.deepcopy(sources["sources"][0]))
        with self.assertRaisesRegex(ContractError, "duplicate source"):
            validate_sources(sources)

    def test_horizon_questions_are_distinct_from_admitted_research(self):
        ids = validate_sources(read_json(ROOT / "docs/research/sources.json"))
        original = read_json(ROOT / "docs/research/hypotheses.json")
        index = next(i for i, row in enumerate(original["hypotheses"])
                     if row["status"] == "horizon")
        for field, value in (("category", "mechanism"), ("question", ""),
                             ("evidence", ["unsupported-claim.json"]),
                             ("status", "testing")):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed["hypotheses"][index][field] = value
                with self.assertRaises(ContractError):
                    validate_hypotheses(changed, ids)
