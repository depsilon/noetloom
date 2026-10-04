#!/usr/bin/env python3
"""Check maintained source/copy boundaries and completed example evidence."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noetloom import __version__
from noetloom.runtime import helper as h
from scripts.build_plugin import BASE, DOMAINS, SKILLS, payload


def same(left, right):
    if left.read_bytes() != right.read_bytes():
        raise ValueError(f"Maintained copy differs: {left.relative_to(ROOT)} from {right.relative_to(ROOT)}")


def main():
    if h.VERSION != __version__:
        raise ValueError("Helper and kit versions differ")
    files = payload()
    if json.loads(files["plugin.json"])["version"] != __version__:
        raise ValueError("Plugin and kit versions differ")
    same(ROOT / "templates/LICENSE", ROOT / "LICENSES/MIT-0.txt")
    for name in ("claude-skill.md", "completed.md"):
        same(ROOT / ".noetloom/templates" / name, ROOT / "templates/base" / name)
    if {p.name for p in (ROOT / "templates/base").iterdir()} != set(BASE):
        raise ValueError("Template inventory and plugin allowlist differ")
    for skill in SKILLS:
        name, _ = h.skill_metadata(h.read_text(ROOT / ".agents/skills" / skill / "SKILL.md"))
        if name != skill:
            raise ValueError(f"Skill directory/name mismatch: {skill}")
    for domain in DOMAINS:
        name, _ = h.skill_metadata(h.read_text(ROOT / "templates/domains" / domain / "SKILL.md"))
        if name != f"project-{domain}":
            raise ValueError(f"Domain skill name mismatch: {domain}")
    if {p.name for p in (ROOT / "noetloom").glob("*.py")} != {"__init__.py", "__main__.py", "bootstrap.py", "runtime.py"}:
        raise ValueError("Framework module inventory and package boundary differ")
    examples = (ROOT / "examples/expense-totals", ROOT / "examples/reading-list")
    for root in (ROOT, *examples):
        project = h.Project(root)
        result = project.check()
        if result["status"] != "passed":
            raise ValueError(str(result))
        state = project.status()
        if state["pending_feedback"] or state["unacknowledged_feedback"]:
            raise ValueError(f"Unreconciled input in {root.name}")
        if root == ROOT:
            continue
        if state["status"] != "complete":
            raise ValueError(f"Maintained example is unfinished: {root.name}")
        same(root / ".noetloom/project.py", ROOT / ".noetloom/project.py")
        for name in ("claude-skill.md", "completed.md"):
            same(root / ".noetloom/templates" / name, ROOT / "templates/base" / name)
        for skill in SKILLS[1:]:
            same(root / ".agents/skills" / skill / "SKILL.md", ROOT / ".agents/skills" / skill / "SKILL.md")
        domain = project.manifest["domain"]
        same(root / f".agents/skills/project-{domain}/SKILL.md", ROOT / f"templates/domains/{domain}/SKILL.md")
        for source, target in (("LICENSE", "Apache-2.0.txt"), ("NOTICE", "NOTICE"),
                               ("LICENSES/MIT-0.txt", "MIT-0.txt"), ("templates/base/license-scope.md", "README.md")):
            same(root / ".noetloom/licenses" / target, ROOT / source)
        result = subprocess.run([sys.executable, "-I", "-B", str(root / ".noetloom/project.py"), "check"],
                                cwd=root, capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise ValueError(result.stderr or result.stdout)
    for name, data in files.items():
        if any(private in data for private in (b"/.codex/skills/", b"sl-dh-", b"/Users/", b"noetloom-local-repo")):
            raise ValueError(f"Personal dependency leaked into plugin: {name}")
    print(f"Kit, {len(SKILLS)} canonical plugin skills, licenses, adapters, and 2 completed applications agree.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        print(f"Kit check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
