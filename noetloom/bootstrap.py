"""Install a small, self-contained framework without rewriting an application."""
from __future__ import annotations

import json
from pathlib import Path
import re
import uuid

from .runtime import KIT_ROOT, helper as h

DOMAINS = ("utility", "website", "data", "deployment")
LIFECYCLE = ("noetloom-intake", "noetloom-work", "noetloom-verify")
START = "<!-- noetloom:instructions -->"
END = "<!-- /noetloom:instructions -->"


def bootstrap(target, *, name, prompt, domain="utility", adopt=False, compact=False,
              docs_dir="docs", example=False):
    h.require(isinstance(name, str) and name.strip() and "\n" not in name, "Use a nonempty single-line project name")
    h.require(isinstance(prompt, str) and prompt.strip(), "A project request is required")
    h.require(len(prompt.encode()) <= 128 * 1024, "Project request exceeds 128 KiB")
    h.require(domain in DOMAINS, "Unknown domain")
    selected = Path(target).expanduser().absolute()
    h.require(not selected.is_symlink(), "Select the actual project directory, not a symlink")
    root = selected.resolve()
    h.require(root != KIT_ROOT, "Bootstrap targets another project, not the Noetloom checkout")
    if root.is_relative_to(KIT_ROOT):
        h.require(example and root.is_relative_to(KIT_ROOT / "examples") and root != KIT_ROOT / "examples",
                  "Applications belong outside Noetloom; --example is only for maintained examples/<name>")
    h.require(not root.exists() or root.is_dir(), "Target is not a directory")
    docs = h.safe(root, docs_dir).relative_to(root).as_posix()
    h.require(docs not in {".", ".noetloom", ".agents", ".claude", ".git"}
              and not docs.startswith((".noetloom/", ".agents/", ".claude/", ".git/")), "Choose a document directory")
    request = {"name": name, "prompt": prompt, "domain": domain, "compact": compact, "docs_dir": docs}
    manifest_path = h.safe(root, ".noetloom/manifest.json")
    if manifest_path.exists():
        project = h.Project(root)
        h.require(project.manifest.get("bootstrap_request") == request,
                  "Project already exists with a different request; reconcile new feedback in that project")
        result = project.check()
        h.require(result["status"] == "passed", "Existing framework needs repair: " + "; ".join(result["errors"]))
        return {"status": "existing", "root": str(root), "project_id": project.id,
                "next": "Read AGENTS.md and project status; no files were changed."}
    h.require(not root.exists() or not any(root.iterdir()) or adopt,
              "Nonempty target requires --adopt after inspecting its existing instructions and code")
    h.require(not h.safe(root, ".noetloom").exists(), "Unrecognized .noetloom directory; inspect before adoption")
    project_id = str(uuid.uuid4())
    roles = {"project": f"{docs}/project.md", "architecture": f"{docs}/architecture.md",
             "plan": f"{docs}/plan.md", "validation": f"{docs}/validation.md", "completed": f"{docs}/completed.md"}
    if compact:
        roles.update(architecture=roles["project"], completed=roles["plan"])

    def template(filename):
        text = h.read_text(KIT_ROOT / "templates/base" / filename)
        # Substitute only original template tokens; prompt content is not another template.
        values = {"NAME": name, "DOMAIN": domain, "PROMPT": prompt,
                  **{role.upper() + "_PATH": path for role, path in roles.items()}}
        return re.sub(r"@(" + "|".join(values) + r")@", lambda match: values[match[1]], text)

    instructions = template("AGENTS.md")
    agents = h.safe(root, "AGENTS.md")
    def existing_text(path):
        if not path.exists():
            return ""
        h.read_text(path)  # Apply the same size/type/encoding admission checks.
        with path.open(encoding="utf-8", newline="") as stream:
            return stream.read()

    old_agents = existing_text(agents)
    h.require(START not in old_agents, "Existing Noetloom instruction block lacks a recognized manifest")
    agents_text = (old_agents + "\n\n" if old_agents else "") + START + "\n" + instructions + END + "\n"
    claude = h.safe(root, "CLAUDE.md")
    claude_text = existing_text(claude)
    if "@AGENTS.md" not in claude_text.splitlines():
        claude_text = claude_text + ("\n\n" if claude_text else "") + template("CLAUDE.md")
    plan = h.read_json(KIT_ROOT / "templates/base/plan.json")
    plan["items"][0]["outcome"] = "Derive concrete implementation phases for: " + prompt
    files = {"AGENTS.md": agents_text, "CLAUDE.md": claude_text,
             ".noetloom/project.py": h.read_text(KIT_ROOT / ".noetloom/project.py"),
             ".noetloom/operating-model.md": h.read_text(KIT_ROOT / "docs/operating-model.md"),
             ".noetloom/helpers.md": h.read_text(KIT_ROOT / "docs/helpers.md"),
             ".noetloom/licenses/Apache-2.0.txt": h.read_text(KIT_ROOT / "LICENSE"),
             ".noetloom/licenses/NOTICE": h.read_text(KIT_ROOT / "NOTICE"),
             ".noetloom/licenses/MIT-0.txt": h.read_text(KIT_ROOT / "LICENSES/MIT-0.txt"),
             ".noetloom/licenses/README.md": template("license-scope.md"),
             ".noetloom/templates/claude-skill.md": template("claude-skill.md"),
             ".noetloom/templates/completed.md": template("completed.md"),
             roles["project"]: template("project.md"),
             roles["plan"]: template("plan.md").replace("@PLAN@", h.block("plan", plan)),
             roles["validation"]: template("validation.md")}
    if compact:
        files[roles["project"]] += "\n" + template("architecture.md")
        files[roles["plan"]] += "\n" + template("completed.md")
    else:
        files[roles["architecture"]] = template("architecture.md")
    skills = [*LIFECYCLE, f"project-{domain}"]
    for skill in skills:
        canonical = KIT_ROOT / ".agents/skills"
        if not canonical.is_dir():  # Portable plugin distribution uses the same canonical bytes.
            canonical = KIT_ROOT / "skills"
        source = (KIT_ROOT / "templates/domains" / domain / "SKILL.md" if skill.startswith("project-")
                  else canonical / skill / "SKILL.md")
        text = h.read_text(source)
        actual_name, description = h.skill_metadata(text)
        h.require(actual_name == skill, "Skill source name disagrees with its directory")
        files[f".agents/skills/{skill}/SKILL.md"] = text
        files[f".claude/skills/{skill}/SKILL.md"] = h.adapter_text(skill, description, text)
    manifest = {"schema": "noetloom.project.v1", "project_id": project_id, "name": name,
                "kit_version": h.VERSION, "domain": domain, "roles": roles,
                "skills": [f".agents/skills/{x}" for x in skills], "bootstrap_request": request}
    files[".noetloom/manifest.json"] = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    checkpoint = h.read_json(KIT_ROOT / "templates/base/checkpoint.json")
    checkpoint.update(project_id=project_id, plan_sha256=h.digest(files[roles["plan"]]))
    files[".noetloom/checkpoint.json"] = json.dumps(checkpoint, indent=2) + "\n"
    # Check every target before the first write. Only instruction imports may append to existing files.
    originals = {}
    for relative in files:
        path = h.safe(root, relative)
        h.require(not path.exists() or relative in {"AGENTS.md", "CLAUDE.md"}, f"Adoption conflict: {relative}")
        h.require(not path.exists() or path.is_file(), f"Target is not a file: {relative}")
        originals[relative] = existing_text(path) if path.exists() else None
        for ancestor in path.parents:
            if ancestor == root:
                break
            h.require(not ancestor.exists() or ancestor.is_dir(), f"Parent is not a directory: {ancestor}")
    root.mkdir(parents=True, exist_ok=True)
    written = []
    try:
        for relative, text in files.items():
            h.atomic_write(h.safe(root, relative), text)
            written.append(relative)
    except OSError:
        # Restore only paths written by this attempt; never clean unrelated application files.
        for relative in reversed(written):
            path = h.safe(root, relative)
            if originals[relative] is None:
                path.unlink(missing_ok=True)
            else:
                h.atomic_write(path, originals[relative])
        raise
    return {"status": "created", "root": str(root), "project_id": project_id,
            "next": "Read AGENTS.md and the local operating method. Replace the planning sentinel with project-specific phases and checks, then drive development through the agreed completion boundary.",
            "application_implemented": False}
