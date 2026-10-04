# Noetloom

Create and maintain project-specific agent workflows with persistent requirements,
feedback reconciliation, resumable plans, and evidence-backed delivery.

Use the installed `noetloom-bootstrap` skill to create or adopt a workspace and
begin implementing the request. The bundled [BOOTSTRAP.md](BOOTSTRAP.md) is the
entrypoint. Lifecycle skills operate in the selected generated project, whose local
records remain usable after uninstalling this plugin.

This package contains the same canonical skills and helper as the reference
repository. Python 3.11+ and workspace file access are needed for its helpers;
the host supplies both execution and permissions. There is no MCP server, model
API, lifecycle hook, telemetry service, or background listener.

See [host support](docs/hosts.md), [licensing](docs/licensing.md), and
[privacy](docs/privacy.md). The framework is Apache-2.0; designated original
templates are MIT-0. An independent application keeps its own licensing policy.

The package is prepared for review. Directory submission, approval, and publication
are separate actions and have not occurred. Support: https://github.com/depsilon/noetloom/issues.
