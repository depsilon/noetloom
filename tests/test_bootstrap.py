import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from noetloom.bootstrap import bootstrap, DOMAINS
from noetloom.runtime import KIT_ROOT, helper as h


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"

    def create(self, **kwargs):
        return bootstrap(self.root, name="A small project", prompt="Compute useful totals.", **kwargs)

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_new_project_is_self_contained_and_initial_application_check_fails(self):
        self.create()
        project = h.Project(self.root)
        self.assertEqual(project.check()["status"], "passed")
        self.assertEqual(project.status()["status"], "blocked")
        self.assertIsNone(project.status()["next"])
        self.assertEqual(project.plan()[0]["id"], "P-000")
        self.assertEqual(project.verify(["application"])[0]["status"], "failed")
        self.assertFalse((self.root / "docs/completed.md").exists())
        self.assertFalse((self.root / "docs/decisions").exists())
        env = dict(os.environ, PYTHONPATH="")
        result = subprocess.run([sys.executable, "-I", "-B", str(self.root / ".noetloom/project.py"), "status"],
                                cwd=self.temp.name, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "blocked")
        self.assertEqual((self.root / ".noetloom/project.py").read_bytes(), (KIT_ROOT / ".noetloom/project.py").read_bytes())
        self.assertFalse((self.root / "LICENSE").exists())
        self.assertEqual((self.root / ".noetloom/licenses/Apache-2.0.txt").read_bytes(), (KIT_ROOT / "LICENSE").read_bytes())
        self.assertEqual((self.root / ".noetloom/licenses/MIT-0.txt").read_bytes(), (KIT_ROOT / "LICENSES/MIT-0.txt").read_bytes())
        for guide in ("operating-model.md", "helpers.md"):
            self.assertEqual((self.root / ".noetloom" / guide).read_bytes(), (KIT_ROOT / "docs" / guide).read_bytes())

    def test_planning_sentinel_cannot_complete_with_a_passing_placeholder_check(self):
        self.create()
        project = h.Project(self.root)
        path = self.root / project.roles["validation"]
        checks = {"version": 1, "checks": [{"id": "application", "command": ["{python}", "-c", "pass"],
                   "cwd": ".", "inputs": ["AGENTS.md"], "timeout_seconds": 10}]}
        path.write_text(h.replace_block(path.read_text(), "validation", checks), encoding="utf-8")
        evidence = project.verify(["application"])[0]
        self.assertEqual(evidence["status"], "passed")
        with self.assertRaisesRegex(h.FrameworkError, "Only the next ready item"):
            project.complete("P-000", [evidence["id"]], "Files exist")

    def test_repeat_bootstrap_preserves_bytes_and_identity(self):
        first = self.create(compact=True)
        before = self.files()
        second = self.create(compact=True)
        self.assertEqual(second["status"], "existing")
        self.assertEqual(first["project_id"], second["project_id"])
        self.assertEqual(before, self.files())
        self.assertEqual(h.Project(self.root).history(), ([], {}))

    def test_user_text_is_not_recursively_interpreted_as_template_tokens(self):
        bootstrap(self.root, name="Keep @PROMPT@ literal", prompt="Preserve @NAME@ and @DOMAIN@.")
        self.assertIn("Keep @PROMPT@ literal", (self.root / "AGENTS.md").read_text())
        self.assertIn("Preserve @NAME@ and @DOMAIN@.", (self.root / "docs/project.md").read_text())

    def test_different_prompt_is_feedback_not_rebootstrap(self):
        self.create()
        before = self.files()
        with self.assertRaisesRegex(h.FrameworkError, "different request"):
            bootstrap(self.root, name="A small project", prompt="Replace it all")
        self.assertEqual(before, self.files())

    def test_adoption_preserves_app_and_existing_instructions(self):
        self.root.mkdir()
        (self.root / "app.txt").write_text("user data", encoding="utf-8")
        (self.root / "LICENSE").write_text("My application license", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("Keep my domain rules.\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("Keep my host instructions.\n", encoding="utf-8")
        with self.assertRaisesRegex(h.FrameworkError, "--adopt"):
            self.create()
        self.create(adopt=True, docs_dir="working-docs")
        self.assertEqual((self.root / "app.txt").read_text(), "user data")
        self.assertEqual((self.root / "LICENSE").read_text(), "My application license")
        self.assertTrue((self.root / "AGENTS.md").read_text().startswith("Keep my domain rules.\n"))
        self.assertTrue((self.root / "CLAUDE.md").read_text().startswith("Keep my host instructions.\n"))
        self.assertEqual(h.Project(self.root).roles["plan"], "working-docs/plan.md")
        self.assertIn("[Plan](working-docs/plan.md)", (self.root / "AGENTS.md").read_text())
        self.assertEqual(h.Project(self.root).check()["status"], "passed")

    def test_conflicting_adoption_is_preflighted_before_any_write(self):
        (self.root / "docs").mkdir(parents=True)
        (self.root / "docs/project.md").write_text("My existing specification", encoding="utf-8")
        before = self.files()
        with self.assertRaisesRegex(h.FrameworkError, "Adoption conflict"):
            self.create(adopt=True)
        self.assertEqual(before, self.files())
        self.assertFalse((self.root / ".noetloom").exists())

    def test_file_parent_conflict_is_preflighted(self):
        self.root.mkdir()
        (self.root / ".agents").write_text("belongs to the user", encoding="utf-8")
        before = self.files()
        with self.assertRaises(h.FrameworkError):
            self.create(adopt=True)
        self.assertEqual(before, self.files())

    def test_adoption_preserves_existing_instruction_bytes_including_line_endings(self):
        self.root.mkdir()
        original = b"Existing rules.\r\n\r\nKeep trailing spaces.  \r\n"
        (self.root / "AGENTS.md").write_bytes(original)
        (self.root / "CLAUDE.md").write_bytes(original)
        self.create(adopt=True)
        self.assertTrue((self.root / "AGENTS.md").read_bytes().startswith(original))
        self.assertTrue((self.root / "CLAUDE.md").read_bytes().startswith(original))

    def test_all_domains_and_combined_roles(self):
        for domain in DOMAINS:
            with self.subTest(domain=domain):
                root = Path(self.temp.name) / domain
                bootstrap(root, name=domain, prompt="A scoped request", domain=domain, compact=True)
                project = h.Project(root)
                self.assertEqual(project.roles["project"], project.roles["architecture"])
                self.assertEqual(project.roles["plan"], project.roles["completed"])
                instructions = (root / "AGENTS.md").read_text()
                self.assertIn("[Architecture](docs/project.md)", instructions)
                self.assertIn("[Completion](docs/plan.md)", instructions)
                self.assertEqual(project.check()["status"], "passed")
                self.assertIn(f".agents/skills/project-{domain}", project.manifest["skills"])

    def test_wrong_workspace_and_traversal_are_rejected(self):
        for target in (KIT_ROOT, KIT_ROOT / "customer-portal", KIT_ROOT / "examples"):
            with self.subTest(target=str(target)), self.assertRaises(h.FrameworkError):
                bootstrap(target, name="x", prompt="x")
        for docs in ("../outside", ".noetloom", ".agents/x", "/tmp/outside", "."):
            with self.subTest(docs=docs), self.assertRaises(h.FrameworkError):
                self.create(docs_dir=docs)
        self.assertFalse(self.root.exists())

    @unittest.skipIf(os.name == "nt", "Unprivileged Windows symlink creation is host-dependent")
    def test_symlink_adoption_does_not_write_elsewhere(self):
        self.root.mkdir()
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.root / "docs").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(h.FrameworkError, "Symlink"):
            self.create(adopt=True)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
