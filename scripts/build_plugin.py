#!/usr/bin/env python3
"""Reproducible, allowlisted skills-only package. No download or publication."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("noetloom-bootstrap", "noetloom-intake", "noetloom-work", "noetloom-verify")
BASE = ("AGENTS.md", "CLAUDE.md", "project.md", "architecture.md", "plan.md", "plan.json",
        "validation.md", "completed.md", "claude-skill.md", "checkpoint.json", "license-scope.md")
DOMAINS = ("utility", "website", "data", "deployment")


def payload(root=ROOT):
    mapping = {"plugin.json": "plugin/plugin.json", "README.md": "plugin/README.md",
               "assets/icon.svg": "assets/logo.svg", "assets/README.md": "assets/README.md", "BOOTSTRAP.md": "BOOTSTRAP.md",
               "LICENSE": "LICENSE", "NOTICE": "NOTICE", "LICENSES/MIT-0.txt": "LICENSES/MIT-0.txt",
               "templates/LICENSE": "templates/LICENSE", ".noetloom/project.py": ".noetloom/project.py"}
    for name in ("__init__.py", "__main__.py", "runtime.py", "bootstrap.py"):
        mapping[f"noetloom/{name}"] = f"noetloom/{name}"
    for name in ("hosts.md", "licensing.md", "privacy.md", "operating-model.md", "architecture.md"):
        mapping[f"docs/{name}"] = f"docs/{name}"
    for name in SKILLS:
        mapping[f"skills/{name}/SKILL.md"] = f".agents/skills/{name}/SKILL.md"
    for name in BASE:
        mapping[f"templates/base/{name}"] = f"templates/base/{name}"
    for domain in DOMAINS:
        path = f"templates/domains/{domain}/SKILL.md"
        mapping[path] = path
    for name in ("claude-skill.md", "completed.md"):
        mapping[f".noetloom/templates/{name}"] = f"templates/base/{name}"
    files = {}
    for target, source in sorted(mapping.items()):
        path = root / source
        current = path
        while current != root:
            if current.is_symlink():
                raise ValueError(f"Package source must not be a symlink: {source}")
            current = current.parent
        if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError(f"Missing or oversized package source: {source}")
        # Canonical text, including on Windows checkouts. No timestamps or absolute paths.
        files[target] = path.read_text(encoding="utf-8").encode("utf-8")
    validate_manifest(json.loads(files["plugin.json"]), files)
    provenance = {"schema": "noetloom.bundle.v1", "files": {
        path: {"source": mapping[path], "sha256": hashlib.sha256(data).hexdigest()}
        for path, data in sorted(files.items())}}
    files["bundle.json"] = (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode()
    return files


def validate_manifest(manifest, files):
    allowed = {"$schema", "name", "version", "description", "author", "homepage", "repository",
               "license", "keywords", "extensions"}
    if set(manifest) - allowed or manifest.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
        raise ValueError("Use the supported portable manifest schema")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", manifest.get("name", "")):
        raise ValueError("Invalid plugin name")
    extension = manifest["extensions"]["com.openai"]
    if set(extension) - {"interface", "onboardingSkill"}:
        raise ValueError("This public package is skills-only; hooks, apps, and MCP are not admitted")
    interface = extension["interface"]
    for key, limit in (("displayName", 30), ("shortDescription", 30), ("longDescription", 4000), ("developerName", 80)):
        if not isinstance(interface.get(key), str) or not 0 < len(interface[key]) <= limit:
            raise ValueError(f"Invalid OpenAI interface field: {key}")
    prompts = interface.get("defaultPrompt", [])
    if not 1 <= len(prompts) <= 3 or any(not isinstance(p, str) or not 0 < len(p) <= 128 or "@" in p for p in prompts):
        raise ValueError("Provide one to three plain example prompts")
    for path in (extension["onboardingSkill"], interface["composerIcon"], interface["logo"]):
        if not path.startswith("./") or path[2:] not in files:
            raise ValueError(f"Missing manifest resource: {path}")
    if interface.get("category") != "Developer Tools":
        raise ValueError("Unexpected listing category")


def build(output, root=ROOT):
    files = payload(root)
    output = Path(output)
    if output.exists():
        raise ValueError("Choose a new output directory; the builder does not overwrite files")
    output.mkdir(parents=True)
    package = output / "noetloom"
    for relative, data in sorted(files.items()):
        path = package / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    archive = output / "noetloom.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "noetloom.zip.sha256").write_text(f"{checksum}  noetloom.zip\n", encoding="ascii")
    # Local testing source only; this metadata is deliberately outside the public ZIP.
    marketplace = {"name": "noetloom-local-review", "interface": {"displayName": "Noetloom local review"},
                   "plugins": [{"name": "noetloom", "source": {"source": "local", "path": "./noetloom"},
                                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                                "category": "Developer Tools"}]}
    meta = output / ".agents/plugins/marketplace.json"
    meta.parent.mkdir(parents=True)
    meta.write_text(json.dumps(marketplace, indent=2) + "\n", encoding="utf-8")
    return {"archive": str(archive.resolve()), "package": str(package.resolve()),
            "sha256": checksum, "files": len(files), "published": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/plugin-review")
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output), indent=2))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"Plugin build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
