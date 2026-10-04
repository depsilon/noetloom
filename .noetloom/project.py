#!/usr/bin/env python3
"""Project-local records and checks. This program does not run or call an agent."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import time
import uuid

VERSION = "0.2.0"
FENCE = chr(96) * 3
KINDS = {"question", "suggestion", "requirement", "correction", "instruction",
         "review", "pause", "resume", "unclassified"}
DISPOSITIONS = {"accepted", "merged", "already-addressed", "deferred", "rejected", "answered"}
ROLES = {"project", "architecture", "plan", "validation", "completed"}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}\Z")
MAX_DOCUMENT = 4 * 1024 * 1024


class FrameworkError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise FrameworkError(message)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def identifier(value):
    require(isinstance(value, str) and IDENTIFIER.fullmatch(value), f"Invalid identifier: {value!r}")
    return value


def safe(root, relative):
    """Reject traversal and links below the explicitly selected project root."""
    require(isinstance(relative, str) and relative and "\\" not in relative, "Use a relative POSIX path")
    parts = PurePosixPath(relative).parts
    require(not PurePosixPath(relative).is_absolute() and ".." not in parts, "Path leaves project")
    current = root
    for part in parts:
        current = current / part
        require(not current.is_symlink(), f"Symlink is not a managed project path: {relative}")
    require(current.resolve().is_relative_to(root.resolve()), "Path leaves project")
    return current


def read_text(path):
    require(path.is_file(), f"Missing file: {path}")
    require(path.stat().st_size <= MAX_DOCUMENT, f"Record exceeds {MAX_DOCUMENT} bytes: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeError, OSError) as exc:
        raise FrameworkError(f"Cannot read {path}: {exc}") from exc


def read_json(path):
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise FrameworkError(f"Invalid JSON in {path}: {exc}") from exc


def block_pattern(kind):
    return re.compile(r"(?m)^<!-- noetloom:" + re.escape(kind) + r" -->\n"
                      + FENCE + r"json\n(.*?)\n" + FENCE + r"[ \t]*$", re.S)


def read_block(text, kind):
    matches = list(block_pattern(kind).finditer(text))
    require(len(matches) == 1, f"Expected one noetloom:{kind} JSON block")
    try:
        return json.loads(matches[0].group(1))
    except json.JSONDecodeError as exc:
        raise FrameworkError(f"Invalid {kind} JSON: {exc}") from exc


def block(kind, value):
    return f"<!-- noetloom:{kind} -->\n{FENCE}json\n{json.dumps(value, indent=2, ensure_ascii=False)}\n{FENCE}"


def replace_block(text, kind, value):
    matches = list(block_pattern(kind).finditer(text))
    require(len(matches) == 1, f"Expected one noetloom:{kind} JSON block")
    match = matches[0]
    return text[:match.start()] + block(kind, value) + text[match.end():]


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def skill_metadata(text):
    lines = text.splitlines()
    require(lines and lines[0] == "---" and "---" in lines[1:], "Missing skill frontmatter")
    end = lines[1:].index("---") + 1
    fields = {}
    for line in lines[1:end]:
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            fields[key] = value.strip().strip('"').strip("'")
    name = fields.get("name", "")
    require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) and len(name) < 64, "Invalid skill name")
    require(fields.get("description"), f"Missing description for {name}")
    return name, fields["description"]


def adapter_text(name, description, canonical_text):
    template = read_text(Path(__file__).with_name("templates") / "claude-skill.md")
    values = {"SKILL": name, "DESCRIPTION": json.dumps(description), "SHA256": digest(canonical_text)}
    return re.sub(r"@(SKILL|DESCRIPTION|SHA256)@", lambda match: values[match[1]], template)


class Project:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.meta = safe(self.root, ".noetloom")
        self.manifest = read_json(safe(self.root, ".noetloom/manifest.json"))
        require(isinstance(self.manifest, dict), "Manifest must be an object")
        require(self.manifest.get("schema") == "noetloom.project.v1", "Unsupported project manifest")
        self.id = identifier(self.manifest.get("project_id"))
        self.roles = self.manifest.get("roles", {})
        require(isinstance(self.roles, dict) and set(self.roles) == ROLES, "Manifest must bind the five document roles")
        require(isinstance(self.manifest.get("name"), str) and self.manifest["name"].strip(), "Manifest needs a project name")
        skills = self.manifest.get("skills")
        require(isinstance(skills, list) and all(isinstance(x, str) for x in skills)
                and len(set(skills)) == len(skills), "Manifest needs distinct canonical skill directories")
        for name, relative in self.roles.items():
            require(isinstance(relative, str) and relative.endswith(".md"), f"Invalid {name} owner")
            safe(self.root, relative)
        self.journal = safe(self.root, ".noetloom/transaction.json")

    @contextlib.contextmanager
    def lock(self):
        path = safe(self.root, ".noetloom/.lock")
        with path.open("a+b") as stream:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    if not stream.read(1):
                        stream.write(b"0")
                        stream.flush()
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, BlockingIOError) as exc:
                raise FrameworkError("Another project helper is writing; retry after it exits") from exc
            try:
                yield
            finally:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)

    def clean_transaction(self):
        require(not self.journal.exists(), "Interrupted transaction: inspect status, then run recover")

    def document(self, role):
        return read_text(safe(self.root, self.roles[role]))

    def data(self, role):
        value = read_block(self.document(role), role)
        require(isinstance(value, dict) and value.get("version") == 1, f"Unsupported {role} block")
        return value

    def role_hashes(self):
        return {role: digest(self.document(role)) for role in self.roles}

    def events(self):
        path = safe(self.root, ".noetloom/feedback.jsonl")
        if not path.exists():
            return []
        rows = []
        for number, line in enumerate(read_text(path).splitlines(), 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise FrameworkError(f"Malformed feedback line {number}; do not discard it") from exc
            require(isinstance(row, dict), f"Feedback line {number} must be an object")
            require(row.get("project_id") == self.id, "Feedback belongs to another project")
            require(row.get("sequence") == number, "Feedback sequence is incomplete")
            rows.append(row)
        return rows

    def receipts(self):
        result = {}
        for event in self.events():
            key = identifier(event.get("id"))
            action = event.get("event")
            if action == "recorded":
                require(key not in result and event.get("kind") in KINDS, "Duplicate or invalid feedback")
                result[key] = {**event, "original_kind": event["kind"],
                               "recorded_sequence": event["sequence"], "state": "recorded"}
            elif action == "classified":
                require(key in result and result[key]["state"] == "recorded", "Classification requires pending feedback")
                require(result[key]["kind"] == "unclassified" and event.get("kind") in KINDS - {"unclassified"},
                        "Only unclassified input can be classified")
                result[key].update(kind=event["kind"])
            elif action == "applied":
                require(key in result and result[key]["state"] == "recorded", "Invalid feedback application")
                require(event.get("disposition") in DISPOSITIONS, "Invalid feedback disposition")
                result[key].update(event, state="applied")
                for earlier in event.get("supersedes", []):
                    require(earlier in result and earlier != key, "Unknown superseded feedback")
                    result[earlier]["superseded_by"] = key
            elif action == "acknowledged":
                require(key in result and result[key]["state"] == "applied", "Acknowledgement precedes application")
                result[key].update(acknowledgement=event["message"], acknowledged_at=event["at"],
                                   state="acknowledged")
            else:
                raise FrameworkError(f"Unknown feedback event: {action}")
        return result

    def event_update(self, event):
        rows = self.events()
        rows.append({**event, "sequence": len(rows) + 1, "project_id": self.id, "at": now()})
        return "\n".join(encoded(row) for row in rows) + "\n"

    def checkpoint(self):
        path = safe(self.root, ".noetloom/checkpoint.json")
        if not path.exists():
            return {"project_id": self.id, "paused": False}
        result = read_json(path)
        require(isinstance(result, dict), "Checkpoint must be an object")
        require(result.get("project_id") == self.id, "Checkpoint belongs to another project")
        require(type(result.get("paused")) is bool, "Checkpoint lacks an explicit pause state")
        return result

    def history(self):
        path = safe(self.root, self.roles["completed"])
        if not path.exists():
            return [], {}
        rows = self.data("completed").get("entries")
        require(isinstance(rows, list), "Invalid completion history")
        current = {}
        for row in rows:
            require(isinstance(row, dict), "Completion entry must be an object")
            require(row.get("project_id") == self.id, "Completion belongs to another project")
            if row.get("event") == "completed":
                key = identifier(row["item"]["id"])
                require(key not in current, f"Duplicate completion: {key}")
                require(isinstance(row.get("evidence"), list) and row["evidence"]
                        and all(isinstance(x, str) and IDENTIFIER.fullmatch(x) for x in row["evidence"]),
                        f"Completion lacks valid evidence identifiers: {key}")
                current[key] = row
            elif row.get("event") == "reopened":
                require(row.get("id") in current, "Reopening lacks a prior completion")
                require(row["cycle"] == current[row["id"]]["item"]["cycle"] + 1, "Invalid reopening cycle")
                del current[row["id"]]
            else:
                raise FrameworkError("Invalid completion event")
        return rows, current

    def plan(self):
        items = self.data("plan").get("items")
        require(isinstance(items, list), "Plan items must be a list")
        _, completed = self.history()
        by_id = {}
        for item in items:
            require(isinstance(item, dict), "Plan item must be an object")
            key = identifier(item.get("id"))
            require(key not in by_id and key not in completed, f"Duplicate active/completed item: {key}")
            require(item.get("status") in {"planned", "active", "blocked"}, f"Invalid status for {key}")
            require(type(item.get("cycle")) is int and item["cycle"] > 0, f"Invalid cycle for {key}")
            for field in ("title", "outcome"):
                require(isinstance(item.get(field), str) and item[field].strip(), f"{key} needs {field}")
            for field in ("scope", "acceptance", "verification"):
                require(isinstance(item.get(field), list) and item[field]
                        and all(isinstance(x, str) and x.strip() for x in item[field]), f"{key} needs {field}")
            require(isinstance(item.get("depends_on"), list), f"{key} needs dependencies")
            require(item["status"] != "blocked" or item.get("reason"), f"{key} needs a blocking reason")
            by_id[key] = item
        require(sum(x["status"] == "active" for x in items) <= 1, "Only one primary item may be active")
        visited, visiting = set(), set()

        def walk(key):
            require(key not in visiting, "Dependency cycle")
            if key in visited:
                return
            visiting.add(key)
            for dependency in by_id[key]["depends_on"]:
                require(dependency in by_id or dependency in completed, f"Unknown dependency: {dependency}")
                if dependency in by_id:
                    walk(dependency)
            visiting.remove(key)
            visited.add(key)
        for key in by_id:
            walk(key)
        return items

    def checks(self):
        rows = self.data("validation").get("checks")
        require(isinstance(rows, list), "Validation checks must be a list")
        result = {}
        for row in rows:
            require(isinstance(row, dict), "Validation check must be an object")
            key = identifier(row.get("id"))
            require(key not in result, f"Duplicate check: {key}")
            command = row.get("command")
            require(isinstance(command, list) and command
                    and all(isinstance(x, str) and x for x in command), "Commands must be argument arrays")
            require(isinstance(row.get("inputs"), list) and row["inputs"], f"{key} needs input patterns")
            for pattern in row["inputs"]:
                safe(self.root, pattern)
                require(not pattern.startswith(".noetloom/evidence"), "Evidence cannot fingerprint itself")
            safe(self.root, row.get("cwd", "."))
            require(type(row.get("timeout_seconds")) in (int, float)
                    and 0 < row["timeout_seconds"] <= 3600, "Check timeout must be in (0, 3600]")
            result[key] = row
        return result

    def snapshot(self, check):
        files = {}
        for pattern in check["inputs"]:
            matches = list(self.root.glob(pattern))
            require(matches, f"Validation input pattern matches nothing: {pattern}")
            count = 0
            for path in matches:
                relative = path.relative_to(self.root).as_posix()
                safe(self.root, relative)
                if path.is_dir():
                    raise FrameworkError(f"Use file patterns, not directory inputs: {pattern}")
                if path.is_file():
                    require(not relative.startswith(".noetloom/evidence/"), "Evidence cannot fingerprint itself")
                    files[relative] = digest(path.read_bytes())
                    count += 1
            require(count, f"No files for validation input: {pattern}")
        return {"definition": digest(encoded(check)), "files": dict(sorted(files.items()))}

    def evidence(self, key):
        identifier(key)
        row = read_json(safe(self.root, f".noetloom/evidence/{key}.json"))
        require(isinstance(row, dict), "Evidence must be an object")
        require(row.get("project_id") == self.id and row.get("id") == key, "Evidence belongs to another project")
        return row

    def fresh(self, evidence):
        checks = self.checks()
        key = evidence.get("check")
        if key not in checks:
            return False
        return (evidence.get("status") == "passed"
                and evidence.get("snapshot") == self.snapshot(checks[key]))

    def stale_completions(self):
        _, current = self.history()
        result = []
        for key, row in current.items():
            checked = set()
            for evidence_id in row.get("evidence", []):
                try:
                    evidence = self.evidence(evidence_id)
                    valid = (self.fresh(evidence)
                             and evidence.get("item_specs", {}).get(key) == digest(encoded(row["item"])))
                    if valid:
                        checked.add(evidence["check"])
                except FrameworkError:
                    valid = False
                if not valid:
                    result.append({"item": key, "evidence": evidence_id})
            if not set(row["item"]["verification"]) <= checked and not any(x["item"] == key for x in result):
                result.append({"item": key, "evidence": "missing required verification"})
        return result

    def adapter_updates(self):
        updates = {}
        for directory in self.manifest.get("skills", []):
            text = read_text(safe(self.root, directory + "/SKILL.md"))
            name, description = skill_metadata(text)
            require(directory == f".agents/skills/{name}", "Canonical skills must live in .agents/skills")
            updates[f".claude/skills/{name}/SKILL.md"] = adapter_text(name, description, text)
        return updates

    def check(self):
        self.clean_transaction()
        for role in self.roles:
            if role != "completed":
                self.document(role)
        items = self.plan()
        checks = self.checks()
        for item in items:
            require(all(key in checks for key in item["verification"]), f"Unregistered verification for {item['id']}")
        self.receipts()
        self.checkpoint()
        errors = []
        for path, expected in self.adapter_updates().items():
            actual = safe(self.root, path)
            if not actual.is_file() or read_text(actual) != expected:
                errors.append(f"Compatibility entry drift: {path}; run adapters")
        claude = safe(self.root, "CLAUDE.md")
        if not claude.is_file() or "@AGENTS.md" not in read_text(claude).splitlines():
            errors.append("CLAUDE.md must import @AGENTS.md")
        stale = self.stale_completions()
        errors.extend(f"Stale completion evidence: {x['item']} / {x['evidence']}" for x in stale)
        return {"status": "passed" if not errors else "failed", "errors": errors,
                "project_id": self.id, "items": len(items), "checks": len(checks)}

    def status(self):
        if self.journal.exists():
            return {"project_id": self.id, "status": "interrupted_transaction",
                    "next": None, "action": "Inspect .noetloom/transaction.json; run recover after resolving conflicts."}
        receipts = self.receipts()
        pending = [r for r in receipts.values() if r["state"] == "recorded"]
        unacknowledged = [r for r in receipts.values() if r["state"] == "applied"]
        checkpoint = self.checkpoint()
        items = self.plan()
        _, completed = self.history()
        stale = self.stale_completions()
        stale_ids = {r["item"] for r in stale}
        ready = [r for r in items if r["status"] in {"active", "planned"}
                 and all(d in completed and d not in stale_ids for d in r["depends_on"])]
        ready.sort(key=lambda r: r["status"] != "active")
        if pending:
            state = "reconcile_feedback"
        elif checkpoint["paused"]:
            state = "paused"
        elif ready:
            state = "ready"
        elif items or stale:
            state = "blocked"
        else:
            state = "complete"
        return {"project_id": self.id, "name": self.manifest["name"], "status": state,
                "next": ready[0] if state == "ready" else None, "roles": self.roles,
                "pending_feedback": pending, "unacknowledged_feedback": unacknowledged,
                "checkpoint": checkpoint, "checkpoint_stale": checkpoint.get("plan_sha256") not in
                {None, digest(self.document("plan"))}, "stale_completions": stale,
                "scope": "Local records only. New conversation input must also be reconciled by the active agent."}

    def commit(self, updates):
        self.clean_transaction()
        writes = []
        for relative, text in updates.items():
            require(isinstance(text, str) and len(text.encode()) <= MAX_DOCUMENT, "Updated record exceeds the 4 MiB limit")
            path = safe(self.root, relative)
            before = digest(path.read_bytes()) if path.exists() else None
            if before != digest(text):
                writes.append({"path": relative, "before": before, "after": digest(text), "text": text})
        if not writes:
            return
        journal_text = encoded({"project_id": self.id, "writes": writes}) + "\n"
        require(len(journal_text.encode()) <= MAX_DOCUMENT, "Transition exceeds the 4 MiB journal limit; reduce record size first")
        atomic_write(self.journal, journal_text)
        self._finish_transaction()

    def _finish_transaction(self):
        journal = read_json(self.journal)
        require(journal.get("project_id") == self.id, "Transaction belongs to another project")
        require(isinstance(journal.get("writes"), list) and journal["writes"], "Empty transaction")
        for row in journal["writes"]:
            path = safe(self.root, row["path"])
            require(digest(row["text"]) == row["after"], "Corrupt transaction content")
            actual = digest(path.read_bytes()) if path.exists() else None
            require(actual in {row["before"], row["after"]},
                    f"Transaction conflicts with an intervening edit: {row['path']}")
        for row in journal["writes"]:
            path = safe(self.root, row["path"])
            actual = digest(path.read_bytes()) if path.exists() else None
            require(actual in {row["before"], row["after"]},
                    f"Transaction conflicts with an intervening edit: {row['path']}")
            if actual != row["after"]:
                atomic_write(path, row["text"])
        self.journal.unlink()

    def recover(self):
        with self.lock():
            require(self.journal.exists(), "No interrupted transaction")
            self._finish_transaction()
            return {"status": "recovered", "project_id": self.id}

    def record(self, key, message, kind, source="user"):
        identifier(key)
        require(kind in KINDS and isinstance(message, str) and message.strip(), "Feedback needs text and kind")
        require(len(message.encode()) <= 128 * 1024, "Feedback exceeds 128 KiB")
        with self.lock():
            self.clean_transaction()
            receipts = self.receipts()
            if key in receipts:
                old = receipts[key]
                require((old["message"], old["original_kind"], old["source"]) == (message, kind, source),
                        "Feedback ID already names different input; use a new ID for a reversal")
                return {"status": "duplicate", "receipt": old}
            hashes = {role: digest(self.document(role)) for role in ROLES
                      if safe(self.root, self.roles[role]).is_file()}
            event = {"event": "recorded", "id": key, "kind": kind, "source": source,
                     "message": message, "owner_hashes_at_recording": hashes}
            self.commit({".noetloom/feedback.jsonl": self.event_update(event)})
            return {"status": "recorded", "id": key}

    def apply(self, key, disposition, summary, roles=(), items=(), supersedes=()):
        require(disposition in DISPOSITIONS and summary.strip(), "Application needs a disposition and summary")
        with self.lock():
            self.clean_transaction()
            receipts = self.receipts()
            require(key in receipts and receipts[key]["state"] == "recorded", "Feedback is not pending")
            original = receipts[key]
            require(original["kind"] != "unclassified", "Classify unclassified input before applying it")
            require(set(roles) <= ROLES, "Unknown owner role")
            require(all(x in receipts and x != key and receipts[x]["state"] != "recorded"
                        and receipts[x]["recorded_sequence"] < original["recorded_sequence"] for x in supersedes),
                    "Supersession must name earlier applied receipts")
            require(not supersedes or original["kind"] in {"correction", "requirement", "instruction", "review", "resume"},
                    "A question or suggestion cannot silently supersede an instruction")
            if original["kind"] in {"question", "suggestion"}:
                require(disposition in {"answered", "deferred", "rejected", "already-addressed"},
                        "Questions and suggestions do not authorize implementation")
            if original["kind"] in {"pause", "resume"}:
                require(disposition == "accepted", "Explicit pause/resume must be accepted")
            current = {role: digest(self.document(role)) for role in roles}
            changing = disposition in {"accepted", "merged"} and original["kind"] not in {"pause", "resume"}
            if changing:
                require(roles and any(original["owner_hashes_at_recording"].get(r) != h
                                      for r, h in current.items()),
                        "Apply the change to its owner documents before marking feedback applied")
            active_ids = {x["id"] for x in self.plan()}
            _, completed = self.history()
            require(all(x in active_ids or x in completed for x in items), "Unknown affected work item")
            if changing:
                require(not any(x in completed for x in items),
                        "Reopen affected completed work before applying changed requirements")
            event = {"event": "applied", "id": key, "disposition": disposition, "summary": summary,
                     "owner_hashes": current, "affected_items": list(items), "supersedes": list(supersedes)}
            updates = {".noetloom/feedback.jsonl": self.event_update(event)}
            if original["kind"] in {"pause", "resume"}:
                cp = self.checkpoint()
                control = receipts.get(cp.get("control_feedback"))
                if control and control["recorded_sequence"] > original["recorded_sequence"]:
                    event["control_effect"] = "superseded by " + control["id"]
                else:
                    cp.update(paused=original["kind"] == "pause", control_feedback=key,
                              pause_reason=summary if original["kind"] == "pause" else None, updated_at=now())
                    updates[".noetloom/checkpoint.json"] = encoded(cp) + "\n"
                    event["control_effect"] = "paused" if cp["paused"] else "resumed"
                updates[".noetloom/feedback.jsonl"] = self.event_update(event)
            self.commit(updates)
            return {"status": "applied", "id": key, "acknowledged": False}

    def classify(self, key, kind):
        with self.lock():
            self.clean_transaction()
            receipt = self.receipts().get(key)
            require(receipt and receipt["state"] == "recorded" and receipt["kind"] == "unclassified",
                    "Only pending unclassified feedback can be classified")
            require(kind in KINDS - {"unclassified"}, "Choose a concrete kind")
            self.commit({".noetloom/feedback.jsonl": self.event_update(
                {"event": "classified", "id": key, "kind": kind})})
            return {"status": "classified", "id": key, "kind": kind}

    def acknowledge(self, key, message):
        require(message.strip(), "Acknowledgement needs the delivered response")
        with self.lock():
            self.clean_transaction()
            receipt = self.receipts().get(key)
            require(receipt and receipt["state"] == "applied", "Only applied feedback can be acknowledged")
            self.commit({".noetloom/feedback.jsonl":
                         self.event_update({"event": "acknowledged", "id": key, "message": message})})
            return {"status": "acknowledged", "id": key,
                    "scope": "Agent attestation of a delivered response; no host transcript was inspected."}

    def save_checkpoint(self, item, next_action):
        with self.lock():
            self.clean_transaction()
            require(item is None or item in {x["id"] for x in self.plan()}, "Checkpoint item is not active work")
            cp = self.checkpoint()
            cp.update(item=item, next_action=next_action, plan_sha256=digest(self.document("plan")), updated_at=now())
            self.commit({".noetloom/checkpoint.json": encoded(cp) + "\n"})
            return cp

    def verify(self, names):
        with self.lock():
            self.clean_transaction()
            require(not self.checkpoint()["paused"], "Project is paused")
            require(not any(r["state"] == "recorded" for r in self.receipts().values()), "Reconcile pending feedback first")
            checks = self.checks()
            require(names and len(set(names)) == len(names) and all(n in checks for n in names), "Unknown or duplicate check")
            results = []
            for name in names:
                check = checks[name]
                before = self.snapshot(check)
                item_specs = {item["id"]: digest(encoded(item)) for item in self.plan()
                              if name in item["verification"]}
                started = time.monotonic()
                command = [sys.executable if x == "{python}" else x for x in check["command"]]
                try:
                    with tempfile.TemporaryFile() as output:
                        process = subprocess.run(command, cwd=safe(self.root, check.get("cwd", ".")),
                                                 stdout=output, stderr=subprocess.STDOUT,
                                                 timeout=check["timeout_seconds"], check=False)
                        output.seek(0)
                        log = output.read(65537)
                    code, error = process.returncode, None
                except (OSError, subprocess.TimeoutExpired) as exc:
                    code, error, log = None, str(exc), b""
                try:
                    after = self.snapshot(check)
                except FrameworkError as exc:
                    after, error = None, str(exc)
                key = "check-" + uuid.uuid4().hex
                passed = code == 0 and before == after
                result = {"schema": "noetloom.check.v1", "project_id": self.id, "id": key,
                          "check": name, "status": "passed" if passed else "failed", "command": command,
                          "cwd": check.get("cwd", "."), "exit_code": code, "error": error,
                          "seconds": time.monotonic() - started, "at": now(), "snapshot": after,
                          "item_specs": item_specs,
                          "inputs_changed_during_check": before != after,
                          "output": log[:65536].decode("utf-8", errors="replace"), "output_truncated": len(log) > 65536}
                self.commit({f".noetloom/evidence/{key}.json": encoded(result) + "\n"})
                results.append(result)
                if not passed:
                    break
            return results

    def complete(self, item_id, evidence_ids, summary):
        require(summary.strip() and evidence_ids, "Completion requires evidence and a summary")
        with self.lock():
            self.clean_transaction()
            status = self.status()
            require(status["status"] == "ready" and status["next"]["id"] == item_id,
                    "Only the next ready item can complete; reconcile, resume or unblock first")
            items = self.plan()
            item = next(x for x in items if x["id"] == item_id)
            evidence = [self.evidence(key) for key in evidence_ids]
            require(all(self.fresh(row) for row in evidence), "Completion evidence is failed or stale")
            require(all(row.get("item_specs", {}).get(item_id) == digest(encoded(item)) for row in evidence),
                    "Work specification changed after verification; rerun its checks")
            require(set(item["verification"]) <= {row["check"] for row in evidence}, "Missing required verification")
            entries, _ = self.history()
            entries.append({"event": "completed", "project_id": self.id, "item": item,
                            "evidence": list(evidence_ids), "summary": summary, "at": now()})
            completed_path = safe(self.root, self.roles["completed"])
            completed_text = read_text(completed_path) if completed_path.exists() else read_text(
                Path(__file__).with_name("templates") / "completed.md")
            updates = {}
            # Multiple roles can share a Markdown file; compose edits against the latest text.
            for role, data in (("plan", {"version": 1, "items": [x for x in items if x["id"] != item_id]}),
                               ("completed", {"version": 1, "entries": entries})):
                path = self.roles[role]
                text = updates.get(path, completed_text if role == "completed" else self.document(role))
                updates[path] = replace_block(text, role, data)
            cp = self.checkpoint()
            cp.update(item=None, next_action="Read status and continue the next authorized ready item.",
                      plan_sha256=digest(updates[self.roles["plan"]]), updated_at=now())
            updates[".noetloom/checkpoint.json"] = encoded(cp) + "\n"
            self.commit(updates)
            return {"status": "completed", "item": item_id, "cycle": item["cycle"]}

    def reopen(self, item_id, reason, feedback_id):
        require(reason.strip(), "Reopening needs a reason")
        with self.lock():
            self.clean_transaction()
            receipt = self.receipts().get(feedback_id)
            require(receipt and receipt["kind"] in {"correction", "requirement", "instruction", "review"},
                    "Reopening must reference a change requirement or accepted review, not a question or pause")
            require(receipt["state"] == "recorded" or receipt.get("disposition") in {"accepted", "merged"},
                    "Deferred or rejected feedback cannot reopen work")
            entries, current = self.history()
            require(item_id in current, "Work item is not currently completed")
            items = self.plan()
            item = dict(current[item_id]["item"])
            item.update(cycle=item["cycle"] + 1, status="planned")
            item.pop("reason", None)
            entries.append({"event": "reopened", "project_id": self.id, "id": item_id,
                            "cycle": item["cycle"], "reason": reason, "feedback": feedback_id, "at": now()})
            updates = {}
            for role, data in (("completed", {"version": 1, "entries": entries}),
                               ("plan", {"version": 1, "items": items + [item]})):
                path = self.roles[role]
                updates[path] = replace_block(updates.get(path, self.document(role)), role, data)
            self.commit(updates)
            return {"status": "reopened", "item": item_id, "cycle": item["cycle"]}

    def adapters(self):
        with self.lock():
            self.clean_transaction()
            updates = self.adapter_updates()
            self.commit(updates)
            return {"status": "synchronized", "entries": list(updates),
                    "scope": "Generated compatibility files; this does not execute Claude Code."}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("status", "check", "recover", "adapters"):
        sub.add_parser(name)
    feedback = sub.add_parser("feedback").add_subparsers(dest="action", required=True)
    record = feedback.add_parser("record")
    record.add_argument("--id", required=True, help="Stable message ID; reuse only for the same delivered input")
    record.add_argument("--kind", choices=sorted(KINDS), required=True)
    record.add_argument("--source", default="user")
    record.add_argument("--message", required=True)
    apply = feedback.add_parser("apply")
    apply.add_argument("--id", required=True)
    apply.add_argument("--disposition", choices=sorted(DISPOSITIONS), required=True)
    apply.add_argument("--summary", required=True)
    apply.add_argument("--roles", nargs="*", default=[])
    apply.add_argument("--items", nargs="*", default=[])
    apply.add_argument("--supersedes", nargs="*", default=[])
    ack = feedback.add_parser("ack")
    ack.add_argument("--id", required=True)
    ack.add_argument("--message", required=True)
    classify = feedback.add_parser("classify")
    classify.add_argument("--id", required=True)
    classify.add_argument("--kind", choices=sorted(KINDS - {"unclassified"}), required=True)
    checkpoint = sub.add_parser("checkpoint")
    checkpoint.add_argument("--item")
    checkpoint.add_argument("--next", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("checks", nargs="+")
    complete = sub.add_parser("complete")
    complete.add_argument("item")
    complete.add_argument("--evidence", nargs="+", required=True)
    complete.add_argument("--summary", required=True)
    reopen = sub.add_parser("reopen")
    reopen.add_argument("item")
    reopen.add_argument("--reason", required=True)
    reopen.add_argument("--feedback", required=True)
    return p


def main(argv=None, root=None):
    args = parser().parse_args(argv)
    try:
        project = Project(root or Path(__file__).absolute().parent.parent)
        if args.command in {"status", "check", "recover", "adapters"}:
            result = getattr(project, args.command)()
        elif args.command == "feedback":
            if args.action == "record":
                result = project.record(args.id, args.message, args.kind, args.source)
            elif args.action == "apply":
                result = project.apply(args.id, args.disposition, args.summary, args.roles, args.items, args.supersedes)
            elif args.action == "classify":
                result = project.classify(args.id, args.kind)
            else:
                result = project.acknowledge(args.id, args.message)
        elif args.command == "checkpoint":
            result = project.save_checkpoint(args.item, args.next)
        elif args.command == "verify":
            rows = project.verify(args.checks)
            result = {"status": "passed" if all(x["status"] == "passed" for x in rows) else "failed",
                      "checks": rows}
        elif args.command == "complete":
            result = project.complete(args.item, args.evidence, args.summary)
        else:
            result = project.reopen(args.item, args.reason, args.feedback)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if isinstance(result, dict) and result.get("status") == "failed" else 0
    except (FrameworkError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
