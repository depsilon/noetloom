"""Validate the binding of a manual browser observation; does not replay a browser."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
report = json.loads((root / "evidence/browser.json").read_text(encoding="utf-8"))
for path, expected in report["sha256"].items():
    actual = hashlib.sha256((root / path).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Browser observation is stale for {path}; inspect the changed UI and record new evidence")
print("Manual browser observation matches its source and screenshot files; no browser was replayed.")
