<img src="assets/logo.svg" alt="Noetloom logo" width="112" height="112">

# Noetloom

**A small working framework for projects built by coding agents.**

Noetloom teaches an existing agent how to turn a request into a project, maintain one
plan, reconcile feedback, verify real results, and resume from files after the original
conversation is gone. The agent builds the application. The project owns its evolving
requirements, skills, decisions, plan, and evidence.

Start with [BOOTSTRAP.md](BOOTSTRAP.md). Give it to Codex, Claude Code, or another capable
coding agent together with your request and a target workspace:

> Use Noetloom to build an offline reading list in ../reading-list. Keep it simple.

The agent can create the local framework with Python 3.11+:

```sh
python3 -B -m noetloom bootstrap ../reading-list --name reading-list --domain website --prompt "Build an offline reading list."
```

Then it reads the generated `AGENTS.md` and starts implementing there. Bootstrap
creates the working structure, **not a finished application**. Its initial application
check deliberately fails until the agent replaces it with meaningful verification.
Use `--adopt` to add the framework to an existing project, or `--compact` to combine
document roles for a small project. Existing application files are never overwritten.
Run the kit from its source checkout; there are no Python package dependencies.

Inside a generated project:

```sh
python3 -B .noetloom/project.py status
python3 -B .noetloom/project.py check
```

New messages pass through intake before work resumes. For example, “work offline;
defer authentication” changes the project requirements and affected work, while
“could we support multiple users eventually?” remains a question. Receipts distinguish
capture, application, and acknowledgement. Completion requires current evidence;
changed requirements reopen the affected work. [The operating guide](docs/operating-model.md)
explains the commands and ownership rules.

There is no daemon, model endpoint, agent runtime, or background listener. Noetloom
guides an active host session and preserves enough local state for the next one.
It cannot capture messages that never reach the project, authenticate a receipt's
author, or establish correctness from a passing command alone.

- [Working examples](examples/README.md): a CSV command-line utility and an offline website.
- [OpenAI plugin](docs/plugin.md): reproducible skills-only packaging and tested local installation.
- [Host support and evidence](docs/hosts.md): native Codex exercise, portable instructions,
  and the limits of Claude compatibility checks.
- [Design and reference sources](docs/architecture.md): ownership, execution, and verification.
- [Contributing](CONTRIBUTING.md): local checks and maintenance.

The framework code, lifecycle skills, helper, and documentation are Apache-2.0;
reusable source templates are MIT-0. Generated projects keep those notices under
`.noetloom/licenses/` and receive no automatically imposed framework license or
copyright for their independent application. See [LICENSE](LICENSE), [NOTICE](NOTICE),
and [the licensing guide](docs/licensing.md).
