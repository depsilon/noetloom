# Validation

The suite checks bootstrap/adoption, feedback and continuation state, evidence
freshness, transaction recovery, compatibility entries, and functioning applications.
The kit check validates maintained copies, license boundaries, current example evidence,
and package resources. Archive tests exercise extraction and standalone generation;
actual host installation and native-agent observations are recorded separately below.

<!-- noetloom:validation -->
```json
{
  "version": 1,
  "checks": [
    {
      "id": "suite",
      "command": ["{python}", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
      "cwd": ".",
      "inputs": ["noetloom/*.py", ".noetloom/project.py", ".noetloom/templates/*.md", "templates/base/*.md", "templates/base/*.json", "templates/domains/*/SKILL.md", "templates/LICENSE", ".agents/skills/*/SKILL.md", "tests/*.py", "scripts/*.py", "plugin/*.json", "plugin/*.md", "plugin/assets/*", "LICENSE", "LICENSES/*", "NOTICE", "BOOTSTRAP.md", "docs/hosts.md", "docs/licensing.md", "docs/privacy.md", "docs/operating-model.md", "docs/architecture.md", "examples/**/*.py", "examples/**/*.js", "examples/**/*.cjs", "examples/**/*.html", "examples/**/*.css", "examples/**/*.jpg", "examples/reading-list/evidence/*.json"],
      "timeout_seconds": 300
    },
    {
      "id": "kit",
      "command": ["{python}", "-B", "scripts/check_kit.py"],
      "cwd": ".",
      "inputs": ["noetloom/*.py", ".noetloom/project.py", ".noetloom/templates/*.md", "templates/base/*.md", "templates/base/*.json", "templates/domains/*/SKILL.md", "templates/LICENSE", ".agents/skills/*/SKILL.md", ".claude/skills/*/SKILL.md", "AGENTS.md", "CLAUDE.md", "BOOTSTRAP.md", "README.md", "CONTRIBUTING.md", "LICENSE", "LICENSES/*", "NOTICE", "docs/project.md", "docs/architecture.md", "docs/operating-model.md", "docs/hosts.md", "docs/licensing.md", "docs/privacy.md", "docs/plugin.md", "docs/plugin-review.md", "scripts/*.py", "plugin/*.json", "plugin/*.md", "plugin/assets/*", ".github/workflows/checks.yml", "pyproject.toml", "examples/**/*.py", "examples/**/*.js", "examples/**/*.cjs", "examples/**/*.html", "examples/**/*.css", "examples/**/*.md", "examples/**/*.json", "examples/**/*.jsonl", "examples/**/licenses/*"],
      "timeout_seconds": 120
    }
  ]
}
```

## Observed behavior and limits

On October 4, 2026, the local suite passed 43 tests. This includes nine expense CLI
tests and four Node state tests executed through three example integration cases.
The standalone helper was exercised in new Python processes with isolated imports.
The tests cover idempotent creation, adoption and conflict safety, duplicate feedback,
questions versus instructions, reversals, pause/resume ordering, pending reconciliation,
affected reopening, stale source/check/acceptance evidence, interrupted transactions,
recovery conflicts, cross-project records, locks, and generated adapter drift.

A native Codex agent created the expense utility with only generated project material.
After a correction, question, and pause were captured, a fresh agent received only
the local project and “Continue.” It implemented category filtering, kept full-input
validation, answered the sharing question without adding it to scope, and preserved
deferred databases/authentication. The maintained example keeps those receipts and
completion history. Primary review found and repaired a decimal precision defect;
nine CLI tests now include large whole values plus cents.

The reading-list example was exercised in the Codex in-app browser, including
keyboard creation, error focus, read filtering, removal, reload persistence, and
cached operation with its local preview server stopped. Desktop and 390-pixel-wide
rendered evidence is linked from [the example](../examples/reading-list/docs/validation.md).
The browser receipt is a source-bound manual observation, not browser replay in CI.
Direct file-URL behavior, native mobile browsers, and other browser engines remain
unverified.

The portable plugin was installed with the native Codex CLI. An isolated agent used
its installed resources to create a functioning CSV duplicate-ID utility. A second
fresh agent resumed from local records, applied trimming/lowercase normalization,
and preserved deferred dashboard/database/authentication scope. Package extraction
and post-removal operation are also automated. See [the plugin review record](plugin-review.md).

Claude compatibility entries and canonical links are checked; no Claude Code runtime
was available, so native Claude discovery/execution is not claimed. ChatGPT Directory
submission, automatic plugin selection, web/mobile execution, deployment, and background
operation were not exercised. These are explicit proof boundaries, not hidden fallbacks.
