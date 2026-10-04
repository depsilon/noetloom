<img src="assets/logo.svg" alt="Noetloom logo" width="112" height="112">

# Noetloom

**A portable framework for autonomous software development.**

Give an agent an objective and point it to Noetloom. It inspects the real workspace,
establishes project-specific guidance and phased implementation instructions, then
drives implementation, verification, repair, and integration through the agreed
completion boundary. It continues across phases while its host and authority permit.

Start with [BOOTSTRAP.md](BOOTSTRAP.md) and the complete
[operating method](docs/operating-model.md):

> Read Noetloom's BOOTSTRAP.md and operating method. Build an offline reading list
> in ../reading-list. Deliver working local behavior, tests, and usage instructions.
> Derive the phases and relevant project guidance, implement them, inspect and repair
> the result, and continue until that boundary is met. Accounts and cloud sync are deferred.

The baseline is ordinary written instructions and project files. Any capable agent or
human can read them explicitly and use normal application tools. No Noetloom Python
command, fenced JSON record, native skill discovery, adapter, or plugin is required.
Project generation initializes the environment; it is only the beginning of development.

The agent derives meaningful phases from the objective, dependencies, and risks.
Each phase names a concrete outcome, work instructions, relevant guidance, acceptance,
and verification. The plan evolves when evidence reveals necessary missing work.
Routine engineering choices and phase transitions do not require repeated "continue"
prompts. External actions still require their actual authority.

New messages steer this ongoing process. Corrections update the relevant requirements
and work; questions do not silently become features. Local instructions preserve deferred
scope, explicit reversals, useful evidence, and enough state for a fresh session to resume.
Noetloom cannot keep an exited host running or receive conversations it was never given.

- [Readable project outlines and domain guidance](templates/README.md).
- [Working examples and proof boundaries](examples/README.md).
- [Optional Python helpers](docs/helpers.md), [host conveniences](docs/hosts.md), and
  [skills-only OpenAI plugin](docs/plugin.md).
- [Design and references](docs/architecture.md) and [contributing](CONTRIBUTING.md).

Copyright 2026 **Dylan Justin Heinrich**. Licensing notice updated **October 4, 2026**.

- Framework, lifecycle guidance, helpers, documentation, plugin integration and maintained
  example applications: **Apache-2.0**.
- Designated original starter templates: **MIT-0**, allowing reuse without attribution.
- Independently built applications: **their own licensing policy**. Using Noetloom does
  not assign your application's copyright to Noetloom or require either framework license.

The licenses apply to their respective components. Preserve applicable notices for copied
framework and third-party material. See [LICENSE](LICENSE), [NOTICE](NOTICE), and
[the licensing guide](docs/licensing.md).
