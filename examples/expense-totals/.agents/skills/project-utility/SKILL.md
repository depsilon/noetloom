---
name: project-utility
description: Plan, implement, and verify a small utility program with explicit input and output formats, deterministic results, and clear failure behavior.
---

# Utility project guidance

Use this guidance for a command-line tool, script, or focused local utility. Keep the design small unless the request establishes a need to scale it.

## Record in the project and architecture owners

- Identify the user, task, supported input and output formats, and the command or interface they will use.
- Define encoding, field or record structure, ordering, defaults, and whether output is written to stdout, a file, or both.
- Record deterministic behavior, including how equivalent inputs produce equivalent output and what environment-dependent behavior is allowed.
- Specify invalid-input diagnostics, exit codes, and whether partial output can occur before a failure.

## Implementation boundaries

- Keep parsing, validation, transformation, and output responsibilities clear and avoid hidden mutation of input files.
- Reject malformed or unsupported input with actionable diagnostics; never silently drop, truncate, or rewrite data.
- Make overwrite behavior explicit and preserve the original input on failure.
- Do not add a framework, service, or dependency unless the project needs it.

## Verify

- Exercise the actual CLI as a subprocess and check exit status, stdout/stderr, and produced files.
- Cover representative valid input, empty input, malformed input, and boundary cases for each supported format.
- Confirm repeated runs on the same input yield the documented deterministic output.
- Verify failures do not leave corrupted or misleading partial results.
