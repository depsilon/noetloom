# Validation

The application checks invoke the CLI as a user would. They cover exact arithmetic,
refunds, filtering, full-input validation, and errors without partial output.

October 4, 2026 maintenance: the copied NOTICE, MIT-0 text, and license-scope README
match their finalized framework sources byte for byte. This maintenance did not change
application licensing policy; the declared application and framework checks were rerun.

<!-- noetloom:validation -->
```json
{
  "version": 1,
  "checks": [
    {
      "id": "application",
      "command": [
        "{python}",
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-v"
      ],
      "cwd": ".",
      "inputs": [
        "expense_totals.py",
        "tests/*.py"
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
        ".noetloom/operating-model.md",
        ".noetloom/helpers.md",
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
