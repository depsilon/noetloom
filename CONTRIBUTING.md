# Contributing

Read `AGENTS.md`, then use `python3 -B -m noetloom status` to find the current work.
Keep product decisions in `docs/project.md`, active work in `docs/plan.md`, and
completion evidence in `docs/completed.md`. Review findings enter through intake.

The source-checkout kit uses Python 3.11+ and its standard library. Run:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B scripts/check_kit.py
python3 -B -m noetloom check
```

The website example additionally uses Node.js for its application tests. CI runs
both examples and the framework suite on Linux, macOS, and Windows. A browser
exercise is recorded separately; DOM-free unit tests do not establish rendered UX.

Edit lifecycle skills only in `.agents/skills/`. Run
`python3 -B .noetloom/project.py adapters` after changing a canonical skill.
The portable helper's source is `.noetloom/project.py`; generated copies are
snapshots. Update maintained examples deliberately and rerun their checks when
changing the kit. Do not rewrite an adopted project's policies during an upgrade.

Framework contributions use Apache-2.0; designated original `templates/` material uses
MIT-0. See [licensing](docs/licensing.md). Plugin skills are built from the canonical
files; edit the sources, then build into an unused output directory and verify it.
Do not copy private skill content or publish personal
paths. Preserve unrelated work and inspect the diff for accidental artifacts.
