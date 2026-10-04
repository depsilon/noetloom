# Validation

Node tests exercise add/toggle/filter/remove and serialized storage behavior,
including invalid data and unsafe links. Browser observations were made in Codex's
in-app browser at desktop size and 390 × 844. `browser-evidence` checks their source
fingerprints; it does not replay browser interactions or independently prove them.

The observed path was a local HTTP preview followed by a stopped preview server.
Reload, removal, addition, and another reload worked using the service-worker cache.
The list persisted; desktop and mobile screenshots are in `evidence/`. No horizontal
overflow was observed at 390 pixels. Empty-title validation, focus recovery, read
toggle, and unread filtering were exercised. No warning/error console entries were
reported by the browser log tool. Direct `file:` navigation was unavailable in the
test host and is not claimed as verified. Native mobile browsers were not exercised.

<!-- noetloom:validation -->
```json
{
  "version": 1,
  "checks": [
    {
      "id": "application",
      "command": [
        "node",
        "--test",
        "tests/core.test.cjs"
      ],
      "cwd": ".",
      "inputs": [
        "core.js",
        "app.js",
        "sw.js",
        "index.html",
        "style.css",
        "tests/core.test.cjs"
      ],
      "timeout_seconds": 30
    },
    {
      "id": "browser-evidence",
      "command": [
        "{python}",
        "-B",
        "tests/check_browser_evidence.py"
      ],
      "cwd": ".",
      "inputs": [
        "core.js",
        "app.js",
        "sw.js",
        "index.html",
        "style.css",
        "tests/check_browser_evidence.py",
        "evidence/*"
      ],
      "timeout_seconds": 30
    },
    {
      "id": "framework",
      "command": [
        "{python}",
        "-B",
        ".noetloom/project.py",
        "check"
      ],
      "cwd": ".",
      "inputs": [
        ".noetloom/project.py",
        ".noetloom/manifest.json",
        ".noetloom/templates/*.md",
        ".noetloom/licenses/*",
        ".agents/skills/*/SKILL.md",
        ".claude/skills/*/SKILL.md",
        "AGENTS.md",
        "CLAUDE.md"
      ],
      "timeout_seconds": 30
    }
  ]
}
```
