# Validation

The application checks invoke the CLI as a user would. They cover exact arithmetic,
refunds, filtering, full-input validation, and errors without partial output.

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
