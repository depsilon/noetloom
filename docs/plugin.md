# Optional OpenAI plugin distribution

Noetloom's complete baseline is the readable [bootstrap entrypoint](../BOOTSTRAP.md)
and [operating method](operating-model.md). They work with any capable agent or human
using ordinary project files and the host's normal development tools. The plugin is an
optional convenience for native discovery and the Python helper profile; it is not a
prerequisite for autonomous development. The portable skills-only package contains
canonical skills, bootstrap resources, original templates, and the project helper.
Packaging adds no MCP server, model runtime, lifecycle hooks, or host permissions.
Generated projects keep their own local files and continue to work after uninstalling
the plugin.

## Build and inspect

In a source checkout, building the optional package requires Python 3.11+:

```sh
python3 -B scripts/build_plugin.py --output dist/plugin-review
python3 -B -m unittest discover -s tests -p test_plugin.py -v
```

Choose an unused output directory; the builder never overwrites one. It emits a
`noetloom/` directory, `noetloom.zip`, its SHA-256 file, and local-test marketplace
metadata outside the ZIP. The ZIP has a root `plugin.json`, `skills/`, and explicit
resource files; OpenAI metadata lives in `extensions.com.openai`. Its allowlist excludes
project records, private skills, caches, hooks, app references, and MCP configuration.
Fixed timestamps, permissions, sorted entries, and stored ZIP data make identical
source bytes produce identical archives. `bundle.json` records each packaged file's
source and hash. This is a local consistency check, not OpenAI's submission validator.

## Local installation

On a Codex host offering the plugin CLI:

```sh
codex plugin marketplace add /absolute/path/to/dist/plugin-review --json
codex plugin add noetloom@noetloom-local-review --json
codex plugin list --json
```

The local marketplace exists only to exercise installation. It is not a hosted
marketplace or product dependency. Remove the test installation with `codex plugin
remove noetloom@noetloom-local-review`, then `codex plugin marketplace remove
noetloom-local-review`. Never replace an unrelated marketplace or installed plugin.
Desktop discovery may require a new session or app restart; installing resources is
not proof of automatic skill activation in every host.

The host must provide the ordinary workspace and application tools needed for the
chosen project. Python 3.11+ is required only for the optional helper profile and this
package build. Noetloom cannot add local filesystem access to a web/mobile session. If
the host lacks tools needed to create or verify the application, the agent must not
claim it did so. Feedback intake applies only to delivered messages or an explicitly
connected source. See [host evidence](hosts.md) and [privacy](privacy.md).

## Review and publication boundary

The package is prepared for review, with four related workflows: bootstrap, intake,
continuation, and verification. [Plugin review notes](https://github.com/depsilon/noetloom/blob/main/docs/plugin-review.md) record exercised
paths and limitations. No package has been submitted or published to the Directory.
An explicit later authorization is required for either action.

Official guidance checked on October 4, 2026:

- [Portable packaging](https://developers.openai.com/plugins/build/plugins) supports
  a root manifest and autodiscovered skills, with OpenAI metadata in its extension.
- [Submission](https://developers.openai.com/plugins/deploy/submission) currently excludes
  lifecycle hooks and app-reference packages. It also says an MCP server cannot be
  added to an existing skills-only plugin through the update flow. Any future hosted
  service needs a separately planned distribution decision.
- [Directory guidelines](https://developers.openai.com/plugins/plugin-guidelines) require
  useful, reliable, complete workflows, accurate listing metadata, a published privacy
  policy, support contact details, and verified developer identity. Skills-only packages
  may face additional eligibility requirements. Local passing tests do not establish
  eligibility, approval, or availability on web/mobile.
- The [Agent Plugins schema](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json)
  defines portable identity fields. The local checker validates Noetloom's chosen subset;
  the actual Codex installer was exercised separately.

Before a future submission, recheck current requirements, confirm the publisher's
verified identity and support details, and inspect the exact ZIP. This task does not
enroll a developer, accept new terms, upload a package, or seek Directory approval.
