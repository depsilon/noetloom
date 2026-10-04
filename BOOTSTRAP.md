# Build a project with Noetloom

You are the coding agent. Noetloom supplies local instructions and small record
helpers; it does not execute you or generate application code itself.

1. Resolve the user's actual request and workspace. Inspect applicable global,
   ancestor, repository, and directory instructions and the skills actually available
   in your host. Private skills may assist you locally; do not copy them into output
   or make the result depend on their installation. Ask only for information that
   materially blocks work, and keep existing authorization across continuations.
2. Create or adopt the **requested project's directory**, normally outside this
   checkout. A request to build a portal does not authorize editing Noetloom itself.
   Read existing instructions, application code, tests, and Git state before adoption.
3. From this checkout, run `python3 -B -m noetloom bootstrap TARGET --name NAME
   --prompt "REQUEST" --domain utility|website|data|deployment`. Choose one relevant
   overlay; extend it locally when justified. Add `--adopt` for existing nonempty
   directories. Add `--compact` to combine project/architecture and plan/completed
   owners. Conflicting document paths cause an error before writes; use `--docs-dir`
   to choose an unused location. Bootstrap appends a managed routing section to an
   existing AGENTS.md and preserves existing CLAUDE.md content.
4. Change to the generated workspace. Read its AGENTS.md and selected local skills.
   Use `python3 -B .noetloom/project.py` there for project operations; `python3 -m
   noetloom` is the kit's entrypoint, not an installed dependency of the application.
   Refine the project intent, constraints, authority, approach, and coherent plan.
   Replace the initial failing `application` check with checks of real behavior and
   explicit source inputs. Implement the requested application immediately; generated
   folders or a plan are not the requested result.
5. Exercise the real interface, reconcile subsequent messages through intake, and
   complete with current evidence. Use checkpoints to resume after interruption.
   Keep working through authorized ready items while the host session remains active.

Repeating an identical bootstrap validates the installed framework without rewriting
it. A different prompt is new feedback, not a destructive rebootstrap. Generated
projects work with their copied helper and local skills after this kit is unavailable.
No symlink to Noetloom, private skill installation, model API, or background service
is required. Native skill discovery varies by host; see [docs/hosts.md](docs/hosts.md).
