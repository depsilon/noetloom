import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from scripts.build_plugin import ROOT, SKILLS, build, payload, validate_manifest


class PluginTests(unittest.TestCase):
    def test_packaged_guides_have_resolvable_local_markdown_links(self):
        files = payload()
        for name, data in files.items():
            if not name.endswith(".md") or name.startswith("templates/base/"):
                continue  # Base links are rendered against each generated project's owners.
            for target in re.findall(r"\]\(([^)]+)\)", data.decode("utf-8")):
                if target.startswith(("http:", "https:", "#")) or "@" in target or "<" in target:
                    continue
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target.split("#")[0]))
                self.assertTrue(resolved in files or any(p.startswith(resolved + "/") for p in files),
                                f"Packaged link is missing: {name} -> {target}")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_reproducible_archive_contains_only_declared_canonical_resources(self):
        first = build(self.root / "first")
        second = build(self.root / "second")
        self.assertEqual(Path(first["archive"]).read_bytes(), Path(second["archive"]).read_bytes())
        self.assertEqual(first["sha256"], second["sha256"])
        with zipfile.ZipFile(first["archive"]) as archive:
            names = archive.namelist()
            self.assertEqual(names, sorted(names))
            self.assertIn("plugin.json", names)
            for name in names:
                self.assertFalse(name.startswith("/"))
                self.assertNotIn("..", Path(name).parts)
                self.assertNotIn(name, ("mcp.json", ".mcp.json", ".noetloom/feedback.jsonl", ".noetloom/manifest.json"))
                self.assertFalse(name.startswith(("hooks/", "apps/", ".git/", ".codex-plugin/")))
            for name in SKILLS:
                self.assertEqual(archive.read(f"skills/{name}/SKILL.md").decode(),
                                 (ROOT / f".agents/skills/{name}/SKILL.md").read_text(encoding="utf-8"))
            icon = archive.read("assets/icon.svg")
            self.assertEqual(icon, (ROOT / "assets/logo.svg").read_bytes())
            svg = ET.fromstring(icon)
            self.assertEqual(svg.attrib["width"], svg.attrib["height"])
            self.assertGreaterEqual(int(svg.attrib["width"]), 48)
            original = icon.replace(b' width="128" height="128"', b"", 1)
            self.assertEqual(hashlib.sha256(original).hexdigest(),
                             "6107292413cb8e2f4d587c8425542d4724cb8b079fd23246bbcdd049c1377d54")
            provenance = json.loads(archive.read("bundle.json"))
            self.assertEqual(set(provenance["files"]), set(names) - {"bundle.json"})
            for name, record in provenance["files"].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), record["sha256"])

    def test_public_manifest_rejects_hooks_and_missing_resources(self):
        files = payload()
        manifest = json.loads(files["plugin.json"])
        manifest["extensions"]["com.openai"]["hooks"] = "./hooks/hooks.json"
        with self.assertRaisesRegex(ValueError, "skills-only"):
            validate_manifest(manifest, files)
        manifest = json.loads(files["plugin.json"])
        del files["assets/icon.svg"]
        with self.assertRaisesRegex(ValueError, "Missing manifest resource"):
            validate_manifest(manifest, files)

    def test_build_never_overwrites_an_existing_directory(self):
        target = self.root / "existing"
        target.mkdir()
        (target / "user.txt").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not overwrite"):
            build(target)
        self.assertEqual((target / "user.txt").read_text(), "keep")
        self.assertEqual(len(list(target.iterdir())), 1)

    def test_extracted_package_bootstraps_then_generated_project_survives_package_removal(self):
        built = build(self.root / "build")
        installed = self.root / "installed"
        with zipfile.ZipFile(built["archive"]) as archive:
            archive.extractall(installed)
        project = self.root / "application"
        env = dict(os.environ, PYTHONPATH="")
        result = subprocess.run([sys.executable, "-B", "-m", "noetloom", "bootstrap", str(project),
                                 "--name", "Portable project", "--prompt", "Total numbers", "--compact"],
                                cwd=installed, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        shutil.rmtree(installed)  # Disposable extraction only; the copied project must stand alone.
        helper = str(project / ".noetloom/project.py")

        def command(*args):
            run = subprocess.run([sys.executable, "-I", "-B", helper, *args], cwd=project,
                                 env=env, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            return json.loads(run.stdout)

        self.assertEqual(command("check")["status"], "passed")
        command("feedback", "record", "--id", "offline", "--kind", "correction",
                "--message", "Offline only; defer authentication")
        # A separate process resumes with no originating conversation or installed package.
        pending = command("status")
        self.assertEqual(pending["status"], "reconcile_feedback")
        self.assertEqual(pending["pending_feedback"][0]["id"], "offline")
        owner = project / "docs/project.md"
        owner.write_text(owner.read_text(encoding="utf-8") + "\nOffline required; authentication deferred.\n", encoding="utf-8")
        command("feedback", "apply", "--id", "offline", "--disposition", "accepted", "--summary", "Owner updated",
                "--roles", "project", "--items", "P-000")
        ready = command("status")
        self.assertEqual(ready["status"], "blocked")  # Reconciliation does not derive implementation phases.
        self.assertEqual(ready["unacknowledged_feedback"][0]["id"], "offline")
        self.assertFalse((project / "LICENSE").exists())


if __name__ == "__main__":
    unittest.main()
