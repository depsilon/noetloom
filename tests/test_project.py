import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from noetloom.bootstrap import bootstrap
from noetloom.runtime import helper as h


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        bootstrap(self.root, name="test", prompt="Total numbers", compact=True)
        self.project = h.Project(self.root)
        # State-machine tests use a deliberately authored implementation phase.
        # Bootstrap itself provides only a blocked planning sentinel.
        self.write_block("plan", {"version": 1, "items": [{
            "id": "P-001", "title": "Compute totals", "status": "planned", "cycle": 1,
            "depends_on": [], "outcome": "Sum numeric values, including empty input",
            "scope": ["Pure numeric total function"],
            "acceptance": ["Mixed positive and negative values sum correctly; empty input yields zero"],
            "verification": ["application"]}]})
        (self.root / "app.py").write_text("def total(values):\n    return sum(values)\n", encoding="utf-8")
        check = {"id": "application", "command": ["{python}", "-B", "-c",
                 "from app import total; assert total([2, 3, -1]) == 4; assert total([]) == 0"],
                 "cwd": ".", "inputs": ["app.py"], "timeout_seconds": 10}
        self.write_block("validation", {"version": 1, "checks": [check]})

    def write_block(self, role, value):
        path = self.root / self.project.roles[role]
        path.write_text(h.replace_block(path.read_text(encoding="utf-8"), role, value), encoding="utf-8")

    def change_project(self, text="Offline only; authentication deferred until explicitly requested."):
        path = self.root / self.project.roles["project"]
        path.write_text(path.read_text(encoding="utf-8") + "\n" + text + "\n", encoding="utf-8")

    def verify(self, check="application"):
        result = self.project.verify([check])[0]
        self.assertEqual(result["status"], "passed", result)
        return result["id"]

    def finish(self, item="P-001", check="application"):
        evidence = self.verify(check)
        self.project.complete(item, [evidence], "Behavior verified")
        return evidence

    def test_completion_moves_work_and_leaves_history_in_shared_document(self):
        evidence = self.finish()
        self.assertEqual(self.project.plan(), [])
        self.assertEqual(self.project.status()["status"], "complete")
        self.assertEqual(self.project.check()["status"], "passed")
        self.assertEqual(self.project.history()[1]["P-001"]["evidence"], [evidence])

    def test_captured_input_blocks_work_until_owners_are_reconciled(self):
        self.project.record("m1", "Offline only, no authentication yet", "correction")
        self.assertEqual(self.project.status()["status"], "reconcile_feedback")
        with self.assertRaisesRegex(h.FrameworkError, "pending feedback"):
            self.project.verify(["application"])
        with self.assertRaisesRegex(h.FrameworkError, "owner documents"):
            self.project.apply("m1", "accepted", "Updated", ["project"], ["P-001"])
        self.change_project()
        self.project.apply("m1", "accepted", "Offline and deferral recorded", ["project"], ["P-001"])
        fresh_session = h.Project(self.root)
        self.assertEqual(fresh_session.status()["status"], "ready")
        self.assertEqual(fresh_session.status()["unacknowledged_feedback"][0]["id"], "m1")
        self.project.acknowledge("m1", "Delivered: offline is required and authentication is deferred.")
        self.assertEqual(h.Project(self.root).status()["unacknowledged_feedback"], [])

    def test_duplicate_delivery_is_idempotent_but_changed_payload_needs_new_id(self):
        self.project.record("m1", "Could we support teams eventually?", "question")
        before = (self.root / ".noetloom/feedback.jsonl").read_bytes()
        self.assertEqual(self.project.record("m1", "Could we support teams eventually?", "question")["status"], "duplicate")
        self.assertEqual(before, (self.root / ".noetloom/feedback.jsonl").read_bytes())
        with self.assertRaisesRegex(h.FrameworkError, "different input"):
            self.project.record("m1", "Build teams now", "instruction")

    def test_questions_and_suggestions_do_not_expand_work(self):
        for kind in ("question", "suggestion"):
            key = "input-" + kind
            self.project.record(key, "Maybe teams later?", kind)
            with self.assertRaisesRegex(h.FrameworkError, "do not authorize"):
                self.project.apply(key, "accepted", "Add teams", ["project"])
            self.project.apply(key, "answered", "Possible later; no implementation requested")
        self.assertEqual(len(self.project.plan()), 1)

    def test_unclassified_capture_can_be_classified_without_rewriting_log(self):
        self.project.record("m1", "Can we do this later?", "unclassified")
        first = (self.root / ".noetloom/feedback.jsonl").read_text()
        with self.assertRaisesRegex(h.FrameworkError, "Classify"):
            self.project.apply("m1", "answered", "Yes")
        self.project.classify("m1", "question")
        self.assertTrue((self.root / ".noetloom/feedback.jsonl").read_text().startswith(first))
        self.assertEqual(self.project.record("m1", "Can we do this later?", "unclassified")["status"], "duplicate")
        self.project.apply("m1", "answered", "Yes; scope unchanged")

    def test_explicit_reversal_supersedes_applied_scope_and_preserves_history(self):
        self.project.record("offline", "Require offline; defer sync", "requirement")
        self.change_project("Offline required; sync deferred.")
        self.project.apply("offline", "accepted", "Offline chosen", ["project"])
        self.project.record("sync", "Now add sync; reverse the offline-only restriction", "instruction")
        self.change_project("Explicit reversal: sync is now in scope; earlier offline-only rule superseded.")
        self.project.apply("sync", "accepted", "Sync authorized", ["project"], supersedes=["offline"])
        self.assertEqual(self.project.receipts()["offline"]["superseded_by"], "sync")
        self.assertEqual(len(self.project.events()), 4)

    def test_pause_survives_checkpoints_and_requires_explicit_resume(self):
        self.project.record("pause", "Pause here", "pause")
        self.project.apply("pause", "accepted", "User paused")
        self.project.save_checkpoint("P-001", "Continue only after user resumes")
        self.assertEqual(h.Project(self.root).status()["status"], "paused")
        with self.assertRaisesRegex(h.FrameworkError, "paused"):
            self.project.verify(["application"])
        self.project.record("resume", "Continue", "resume")
        self.project.apply("resume", "accepted", "Resume durable scope")
        self.assertEqual(h.Project(self.root).status()["status"], "ready")

    def test_acknowledgement_cannot_precede_application(self):
        self.project.record("m1", "Why?", "question")
        with self.assertRaisesRegex(h.FrameworkError, "Only applied"):
            self.project.acknowledge("m1", "Because")

    def test_delayed_older_pause_cannot_override_a_newer_resume(self):
        self.project.record("pause", "Pause", "pause")
        self.project.record("resume", "Continue", "resume")
        self.project.apply("resume", "accepted", "Latest user direction is to continue")
        self.project.apply("pause", "accepted", "Historical pause was superseded")
        self.assertEqual(self.project.status()["status"], "ready")
        self.assertEqual(self.project.receipts()["pause"]["control_effect"], "superseded by resume")

    def test_question_cannot_reopen_completed_work(self):
        self.finish()
        self.project.record("question", "Could we add teams?", "question")
        with self.assertRaisesRegex(h.FrameworkError, "not a question"):
            self.project.reopen("P-001", "Add teams", "question")

    def test_rejected_review_cannot_reopen_completed_work(self):
        self.finish()
        self.project.record("review", "Add teams", "review")
        self.project.apply("review", "rejected", "Outside authorized scope")
        with self.assertRaisesRegex(h.FrameworkError, "rejected"):
            self.project.reopen("P-001", "Add teams", "review")

    def test_completion_history_cannot_change_acceptance_or_drop_evidence_silently(self):
        self.finish()
        data = self.project.data("completed")
        data["entries"][0]["item"]["acceptance"].append("A newly claimed behavior")
        self.write_block("completed", data)
        self.assertEqual(self.project.check()["status"], "failed")
        data["entries"][0]["evidence"] = []
        self.write_block("completed", data)
        with self.assertRaisesRegex(h.FrameworkError, "evidence identifiers"):
            self.project.check()

    def test_oversized_transition_is_rejected_without_corrupting_state(self):
        before = (self.root / ".noetloom/checkpoint.json").read_bytes()
        with self.assertRaisesRegex(h.FrameworkError, "limit"):
            self.project.save_checkpoint("P-001", "x" * h.MAX_DOCUMENT)
        self.assertEqual(before, (self.root / ".noetloom/checkpoint.json").read_bytes())
        self.assertFalse(self.project.journal.exists())

    def test_acceptance_change_invalidates_previously_passing_evidence(self):
        evidence = self.verify()
        plan = self.project.data("plan")
        plan["items"][0]["acceptance"].append("Support fractional numbers")
        self.write_block("plan", plan)
        with self.assertRaisesRegex(h.FrameworkError, "specification changed"):
            self.project.complete("P-001", [evidence], "Done")
        self.finish()

    def test_source_and_check_definition_changes_invalidate_evidence(self):
        evidence = self.verify()
        (self.root / "app.py").write_text("def total(values):\n    return 999\n", encoding="utf-8")
        with self.assertRaisesRegex(h.FrameworkError, "stale"):
            self.project.complete("P-001", [evidence], "Done")
        self.assertEqual(self.project.verify(["application"])[0]["status"], "failed")
        (self.root / "app.py").write_text("def total(values):\n    return sum(values)\n", encoding="utf-8")
        checks = self.project.data("validation")
        checks["checks"][0]["timeout_seconds"] = 9
        self.write_block("validation", checks)
        with self.assertRaisesRegex(h.FrameworkError, "stale"):
            self.project.complete("P-001", [evidence], "Done")

    def test_changed_or_removed_inputs_during_check_record_failure(self):
        for code in ("from pathlib import Path; Path('app.py').write_text('changed')",
                     "from pathlib import Path; Path('app.py').unlink()"):
            (self.root / "app.py").write_text("original", encoding="utf-8")
            checks = self.project.data("validation")
            checks["checks"][0]["command"] = ["{python}", "-c", code]
            self.write_block("validation", checks)
            result = self.project.verify(["application"])[0]
            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["inputs_changed_during_check"])
            self.assertEqual(self.project.evidence(result["id"])["status"], "failed")

    def test_completed_change_reopens_only_affected_item_and_requires_new_evidence(self):
        plan = self.project.data("plan")
        second = copy.deepcopy(plan["items"][0])
        second.update(id="P-002", title="Independent text output", verification=["independent"])
        plan["items"].append(second)
        self.write_block("plan", plan)
        (self.root / "independent.txt").write_text("kept", encoding="utf-8")
        checks = self.project.data("validation")
        checks["checks"].append({"id": "independent", "command": ["{python}", "-c",
                               "from pathlib import Path; assert Path('independent.txt').read_text() == 'kept'"],
                               "cwd": ".", "inputs": ["independent.txt"], "timeout_seconds": 10})
        self.write_block("validation", checks)
        old = self.finish()
        independent = self.finish("P-002", "independent")
        self.project.record("m1", "Change number behavior", "correction")
        self.change_project("Number behavior changed.")
        with self.assertRaisesRegex(h.FrameworkError, "Reopen"):
            self.project.apply("m1", "accepted", "Changed", ["project"], ["P-001"])
        self.project.reopen("P-001", "Changed requirement", "m1")
        self.project.apply("m1", "accepted", "Changed", ["project"], ["P-001"])
        self.assertEqual(self.project.plan()[0]["cycle"], 2)
        self.assertEqual(self.project.history()[1]["P-002"]["evidence"], [independent])
        with self.assertRaisesRegex(h.FrameworkError, "specification changed"):
            self.project.complete("P-001", [old], "Done again")
        self.finish()
        self.assertEqual(self.project.check()["status"], "passed")

    def test_stale_completion_blocks_dependent_work(self):
        plan = self.project.data("plan")
        second = copy.deepcopy(plan["items"][0])
        second.update(id="P-002", depends_on=["P-001"])
        plan["items"].append(second)
        self.write_block("plan", plan)
        self.finish()
        self.assertEqual(self.project.status()["next"]["id"], "P-002")
        (self.root / "app.py").write_text("changed", encoding="utf-8")
        self.assertEqual(self.project.status()["status"], "blocked")
        self.assertEqual(self.project.check()["status"], "failed")

    def test_cross_project_receipts_checkpoints_and_evidence_are_rejected(self):
        evidence = self.verify()
        other_root = Path(self.temp.name) / "other"
        bootstrap(other_root, name="other", prompt="Other work")
        other = h.Project(other_root)
        source = self.root / f".noetloom/evidence/{evidence}.json"
        target = other_root / f".noetloom/evidence/{evidence}.json"
        target.parent.mkdir()
        target.write_bytes(source.read_bytes())
        with self.assertRaisesRegex(h.FrameworkError, "another project"):
            other.evidence(evidence)
        self.project.record("m1", "Why?", "question")
        (other_root / ".noetloom/feedback.jsonl").write_bytes((self.root / ".noetloom/feedback.jsonl").read_bytes())
        with self.assertRaisesRegex(h.FrameworkError, "another project"):
            other.receipts()
        (other_root / ".noetloom/checkpoint.json").write_bytes((self.root / ".noetloom/checkpoint.json").read_bytes())
        with self.assertRaisesRegex(h.FrameworkError, "another project"):
            other.checkpoint()

    def test_interrupted_transition_recovers_after_process_loss(self):
        evidence = self.verify()
        original = h.atomic_write
        calls = []

        def interrupted(path, text):
            calls.append(path)
            if len(calls) == 3:
                raise OSError("simulated process loss after first document write")
            original(path, text)

        with patch.object(h, "atomic_write", interrupted), self.assertRaises(OSError):
            self.project.complete("P-001", [evidence], "Done")
        fresh = h.Project(self.root)
        self.assertEqual(fresh.status()["status"], "interrupted_transaction")
        fresh.recover()
        self.assertEqual(fresh.status()["status"], "complete")
        self.assertEqual(fresh.check()["status"], "passed")

    def test_recovery_preserves_intervening_user_edits(self):
        with patch.object(self.project, "_finish_transaction", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                self.project.save_checkpoint("P-001", "Continue tests")
        checkpoint = self.root / ".noetloom/checkpoint.json"
        content = checkpoint.read_text() + "\n"
        checkpoint.write_text(content, encoding="utf-8")
        with self.assertRaisesRegex(h.FrameworkError, "intervening edit"):
            self.project.recover()
        self.assertEqual(checkpoint.read_text(), content)
        self.assertTrue(self.project.journal.exists())

    def test_lock_serializes_writers_and_releases_after_owner_exits(self):
        command = [sys.executable, "-B", str(self.root / ".noetloom/project.py"), "checkpoint", "--next", "continue"]
        with self.project.lock():
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Another project helper", result.stderr)
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_adapter_drift_is_detected_and_repair_uses_canonical_content(self):
        canonical = self.root / ".agents/skills/noetloom-work/SKILL.md"
        canonical.write_text(canonical.read_text() + "\nA project-specific extension.\n", encoding="utf-8")
        self.assertEqual(self.project.check()["status"], "failed")
        self.project.adapters()
        self.assertEqual(self.project.check()["status"], "passed")
        adapter = (self.root / ".claude/skills/noetloom-work/SKILL.md").read_text()
        self.assertIn(h.digest(canonical.read_text()), adapter)
        self.assertNotIn("A project-specific extension.", adapter)

    def test_invalid_dependency_cycle_and_missing_inputs_fail(self):
        plan = self.project.data("plan")
        plan["items"][0]["depends_on"] = ["P-001"]
        self.write_block("plan", plan)
        with self.assertRaisesRegex(h.FrameworkError, "cycle"):
            self.project.plan()
        plan["items"][0]["depends_on"] = []
        self.write_block("plan", plan)
        checks = self.project.data("validation")
        checks["checks"][0]["inputs"] = ["missing.py"]
        self.write_block("validation", checks)
        with self.assertRaisesRegex(h.FrameworkError, "matches nothing"):
            self.project.verify(["application"])

    def test_failed_or_timed_out_checks_cannot_complete(self):
        checks = self.project.data("validation")
        checks["checks"][0].update(command=["{python}", "-c", "import time; time.sleep(2)"], timeout_seconds=0.05)
        self.write_block("validation", checks)
        failed = self.project.verify(["application"])[0]
        self.assertEqual(failed["status"], "failed")
        self.assertIsNone(failed["exit_code"])
        with self.assertRaisesRegex(h.FrameworkError, "failed or stale"):
            self.project.complete("P-001", [failed["id"]], "Done")


if __name__ == "__main__":
    unittest.main()
