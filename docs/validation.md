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
      "inputs": ["noetloom/*.py", ".noetloom/project.py", ".noetloom/templates/*.md", "templates/base/*.md", "templates/readable/*.md", "templates/README.md", "templates/base/*.json", "templates/domains/*/SKILL.md", "templates/LICENSE", ".agents/skills/*/SKILL.md", "tests/*.py", "scripts/*.py", "plugin/*.json", "plugin/*.md", "assets/*", "LICENSE", "LICENSES/*", "NOTICE", "BOOTSTRAP.md", "docs/hosts.md", "docs/licensing.md", "docs/privacy.md", "docs/operating-model.md", "docs/helpers.md", "docs/evidence/readable-autonomy/*", "docs/evidence/existing-application/*", "docs/architecture.md", "examples/**/*.py", "examples/**/*.js", "examples/**/*.cjs", "examples/**/*.html", "examples/**/*.css", "examples/**/*.jpg", "examples/reading-list/evidence/*.json"],
      "timeout_seconds": 300
    },
    {
      "id": "kit",
      "command": ["{python}", "-B", "scripts/check_kit.py"],
      "cwd": ".",
      "inputs": ["noetloom/*.py", ".noetloom/project.py", ".noetloom/templates/*.md", "templates/base/*.md", "templates/readable/*.md", "templates/README.md", "templates/base/*.json", "templates/domains/*/SKILL.md", "templates/LICENSE", ".agents/skills/*/SKILL.md", ".claude/skills/*/SKILL.md", "AGENTS.md", "CLAUDE.md", "BOOTSTRAP.md", "README.md", "CONTRIBUTING.md", "LICENSE", "LICENSES/*", "NOTICE", "docs/project.md", "docs/architecture.md", "docs/operating-model.md", "docs/helpers.md", "docs/evidence/readable-autonomy/*", "docs/evidence/existing-application/*", "docs/hosts.md", "docs/licensing.md", "docs/privacy.md", "docs/plugin.md", "docs/plugin-review.md", "scripts/*.py", "plugin/*.json", "plugin/*.md", "assets/*", ".github/workflows/checks.yml", "pyproject.toml", "examples/**/*.py", "examples/**/*.js", "examples/**/*.cjs", "examples/**/*.html", "examples/**/*.css", "examples/**/*.md", "examples/**/*.json", "examples/**/*.jsonl", "examples/**/licenses/*", "examples/tool-shelf/reference/*", "examples/tool-shelf/evidence/**/*.txt", "examples/tool-shelf/evidence/**/*.csv", "examples/tool-shelf/evidence/**/*.sqlite3", "examples/tool-shelf/evidence/**/*.zip", "examples/tool-shelf-renewals/reference/*", "examples/tool-shelf-renewals/evidence/**/*.txt", "examples/tool-shelf-renewals/evidence/**/*.csv", "examples/tool-shelf-renewals/evidence/**/*.sqlite3", "examples/tool-shelf-renewals/evidence/**/*.zip", ".gitattributes"],
      "timeout_seconds": 120
    }
  ]
}
```

## Observed behavior and limits

### Licensing attribution and scope, October 4, 2026

Current Noetloom notices and package metadata name **Dylan Justin Heinrich**. Copyright
uses **2026**; the licensing notice is dated **October 4, 2026 (2026-10-04)**. The guide
and generated scope notice distinguish Apache-2.0 framework/example code, MIT-0 designated
templates and independently owned applications. Standard license terms are unchanged.

Current copied notices and fingerprints are refreshed. The two readable applications'
source, tests and recorded execution artifacts are unchanged; their original manifests
retain the historical identities. Their validation records identify the notice correction
and current maintenance source lists. The complete pre-correction examples remain in Git
at `4e5e2b1`. The unpublished plugin candidate is rebuilt with corrected attribution;
its exact artifact and the historical installation evidence are separated in
[the review record](plugin-review.md).

The final local suite passed **48 tests**; the kit and project checks also passed.
Two complete ZIP builds matched byte for byte. Inspection of the extracted final archive
confirmed all 49 payload files matched current sources, full author/developer metadata,
four exact generated license/notice copies, and no application-level LICENSE.

### Existing-application maintenance, unchanged method

On October 4, 2026, a new native agent received the complete 39-test ToolShelf application
and a bounded renewal outcome, with no prepared change plan. It inspected existing
components, derived two extension phases and completed schema migration, CLI/history,
concurrency, recovery and regression work without repeated task selection. Its final
requirements review followed a passing integrated suite and journey; it added a forced
storage-failure rollback check and repaired stale continuation wording. The final native
result passed **54 application tests**, the full journey, **26 documented commands** and
**three previous recovery archives** using ordinary files and Python tools.

The primary froze independent requirement cases before dispatch and the executable runner
before native completion. All ten cases failed against the unchanged baseline as an
expected negative control, then **all ten passed on the first declared candidate** without
repairs. At initial delivery, the maintained example was byte-identical to that candidate. The
[observation](evidence/existing-application/README.md) preserves exact timings, hashes,
first output and separate development, final-review and independent finding categories.

The parent suite now includes both the 54-test extension and independent acceptance;
the original 39-test application's code and tests are unchanged. The kit also validates both readable example
inventories. Operating instructions, canonical skills, helpers, templates and plugin
contents are unchanged: this exercise exposed no concrete framework instruction defect.
At that delivery, the 0.2.0 plugin payload was byte-identical to the previously reviewed package.

Local parent validation passed: `python3.13 -B -m unittest discover -s tests -v`
ran **48 tests in 20.353 seconds**, including both application suites and independent
acceptance. `python3.13 -B scripts/check_kit.py` and `python3.13 -B -m noetloom check`
also passed. The original 39 test methods remain in the extension, with 15 added renewal
tests. Source manifests and current application links were checked separately.

This demonstrates bounded maintenance across existing components and compatibility
contracts, not maturity at production scale or universal defect detection. Native agent
execution and initial acceptance were on macOS/Python 3.13. Hosted tests of the result are
distinct from native execution on another agent host.

[PR #4](https://github.com/depsilon/noetloom/pull/4) at
`052023955760b2df6a719026ec80199ae21156db` passed all three
[hosted workflows](https://github.com/depsilon/noetloom/actions/runs/37235858831):
Linux/Python 3.11, macOS/Python 3.13 and Windows/Python 3.13. It merged as
`0e2a6daaf6ae15e5d7b6b3aa7fa6f7a236232af4`, whose
[main-branch run](https://github.com/depsilon/noetloom/actions/runs/37236064763) also
passed all three. No post-handoff application repair was needed. Windows retains the
existing explicit symlink-privilege skips. The GitHub Codex review bot again reported
exhausted review quota; primary source review, the mechanical evidence audit and frozen
independent acceptance are the review evidence, with no remote automated review claimed.

### Readable autonomous baseline, version 0.2.0

On October 4, 2026, the complete local suite passed 46 framework/integration cases,
including the ToolShelf application's 39-test behavioral suite. The readable method,
phase synthesis and continuity were exercised by a real native-agent build from a brief
and a separate fresh continuation after one mid-project correction. Both sessions used
ordinary local Markdown and application tools. No Noetloom command, discovery directory,
private skill, prepared solution, plugin or original conversation was required.

[The observation record](evidence/readable-autonomy/README.md) preserves the initial
derived plan, interruption state, actual sequence, limits and source fingerprints.
The agent completed 36 tests and the complete CLI journey; primary acceptance found and
fixed a surrounding-whitespace edge case, added regressions, and revalidated 39 tests
and the journey. The example's historical and current evidence remain distinguishable.
The source-fingerprint check detects drift; it does not replay an agent or prove that
Noetloom improves every agent's performance. Native exercise execution was on macOS
Python 3.13. Cross-platform CI results are recorded below when available.

The initial [PR run](https://github.com/depsilon/noetloom/actions/runs/37229650408)
at `e0b377a` passed Linux/Python 3.11 and macOS/Python 3.13. Windows/Python 3.13
exposed seven test-cleanup errors caused by test-owned SQLite connections left open.
Explicit closure preserves their commit/rollback behavior; the application already
closed its own connections. The repaired 39-test application suite passes locally with
resource warnings enabled. [The repaired PR run](https://github.com/depsilon/noetloom/actions/runs/37229930101)
at `4bb70d5` passed all three complete workflows. [PR #3](https://github.com/depsilon/noetloom/pull/3)
merged as `230dd5938c3a9d26395be6275a86fc93db86cc5f`; its
[main-branch run](https://github.com/depsilon/noetloom/actions/runs/37230017496) also passed
Linux/Python 3.11, macOS/Python 3.13 and Windows/Python 3.13. The Windows jobs retain
their explicit symlink-privilege skips. The GitHub Codex review bot reported exhausted
review quota, so no remote automated code review is claimed; primary acceptance and
the local consistency review are the review evidence for this delivery.

Optional-helper regression tests also verify blocked planning sentinels, actual owner
paths for compact/custom document layouts, copied readable guides, preserved feedback
and evidence contracts, and packaged-link completeness. Both earlier helper examples
were refreshed and revalidated without changing their application code or browser images.
The 0.2.0 plugin built reproducibly and its native installed resources and post-removal
project operation passed; [the review record](plugin-review.md) separates that evidence
from the earlier 0.1.0 installed-agent exercise. No Directory submission occurred.

### Earlier framework and host observations, version 0.1.0

Before this refinement, the local suite passed 43 tests. This includes nine expense CLI
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
