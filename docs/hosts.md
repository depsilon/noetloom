# Host support and convenience integrations

Checked against official host documentation on October 4, 2026. Execution observations
are recorded separately in the repository's
[validation record](https://github.com/depsilon/noetloom/blob/main/docs/validation.md).

| Host | Entry and discovery | Scope |
| --- | --- | --- |
| Any capable agent or human | Read `BOOTSTRAP.md`, `docs/operating-model.md`, and the actual project's local instructions and owners | This readable method is the complete baseline. Follow it with ordinary project files and the host's normal development tools; no Noetloom command, Python runtime, JSON records, native discovery, adapters, or plugin is required. |
| Codex | `AGENTS.md` and canonical `.agents/skills/*/SKILL.md` | Native project instructions and skills are a convenience; exercised during this implementation and isolated forward tests. |
| OpenAI portable plugin | Root `plugin.json`, `skills/`, and bundled bootstrap resources | Optional native discovery and helper-profile entry. Codex CLI installation and installed-resource creation/continuation were exercised. ChatGPT Directory, web/mobile execution, and automatic skill selection were not exercised. |
| Claude Code | `CLAUDE.md` imports `@AGENTS.md`; `.claude/skills/*/SKILL.md` links to canonical skills | Generated entries and links are checked locally. Claude Code is unavailable in the development environment; native discovery/execution has not been demonstrated. |

Codex documents project skill discovery under `.agents/skills` and progressive skill
loading in its [skills guide](https://learn.chatgpt.com/docs/build-skills). Claude Code
documents project skills under `.claude/skills` in its
[skills guide](https://code.claude.com/docs/en/skills) and Markdown imports in its
[memory guide](https://code.claude.com/docs/en/memory). The generated Claude files are
small compatibility entries, with canonical hashes checked by the local helper.
They are not separately maintained instructions. No symlink support is required.

Noetloom installs no hooks. Claude's
[hooks reference](https://code.claude.com/docs/en/hooks) documents UserPromptSubmit,
but a host event name alone is not proof that every payload is a newly authorized
human requirement. Any future capture integration must preserve origin and classify
input before changing scope. Hooks are explicitly deferred in the project owner.

The host must provide the ordinary application tools needed by the chosen project,
such as workspace access, its language toolchain, and any relevant test or runtime
environment. Python 3.11+ is needed only for the optional helper profile and package
build. A capable agent can use the written method and the host's normal tools without
Noetloom-specific runtime support. An active host can continue through authorized work
while its session and tools remain available; a fresh session resumes by reading the
local owners and pending feedback. Noetloom cannot listen to conversations it was not
given, wake itself later, or provide autonomous background execution.
