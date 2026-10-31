# Noetloom

Portable instructions for autonomous software development. Give a capable agent an
objective and target workspace; it derives project-specific phases and guidance, then
implements, verifies, repairs, integrates, and continues within the agreed boundary.

The plain written [BOOTSTRAP.md](BOOTSTRAP.md) and
[operating model](docs/operating-model.md) are the complete baseline for any capable
agent or human. Read them directly when native discovery is unavailable. No Noetloom
command, Python runtime, JSON record, skill discovery, adapter, or plugin installation
is required to use the method. This plugin provides optional native discovery and
helper-profile conveniences. Generation initializes a workspace; the active agent
derives real phases and guidance before implementing the objective.

The chosen application determines the ordinary workspace, language, test, and runtime
tools the host must provide. Python 3.11+ is needed only for optional helpers and
building this package. There is no MCP server, model API, lifecycle hook, telemetry
service, or background listener.

Seven canonical skills are included: bootstrap, intake, work, verification,
[repository grounding](skills/noetloom-grounding/SKILL.md),
[context continuity](skills/noetloom-continuity/SKILL.md) and
[subagent orchestration](skills/noetloom-subagents/SKILL.md). New helper-profile projects
receive the six ongoing-work skills and one domain guide. Grounding derives contracts
from the actual repository; continuity resumes the active task after compaction; workers
are used only when available, permitted and independently useful. No fixed model or
repository is required. The full procedures remain readable in the operating method.

Copyright 2026 **Dylan Justin Heinrich**. Licensing notice updated **October 4, 2026**.
The framework is **Apache-2.0**; designated original templates are **MIT-0**.
These licenses apply to separate components. An independent application keeps its own
licensing policy and copyright; Noetloom does not assign it a framework license.
See [host support](docs/hosts.md), [licensing](docs/licensing.md), and
[privacy](docs/privacy.md).

The package is prepared for review. Directory submission, approval, and publication
are separate actions and have not occurred. Support: https://github.com/depsilon/noetloom/issues.
