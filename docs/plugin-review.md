# Plugin review record

Prepared October 4, 2026. This is a local review candidate, not a Directory submission
or an approval claim. Public submission/publication remains explicitly unauthorized.

## Candidate identity

- Version: `0.1.0`; portable root `plugin.json`; four canonical skills.
- Build: `python3 -B scripts/build_plugin.py --output dist/plugin-review`.
- Review ZIP SHA-256: `a86e6cb23488a8c9706bc3f5cc1333ed6ecd16d44c7fa068f9876f31e3965d0d`.
- Contents: 41 files, including `bundle.json` with source mappings and hashes for
  the other 40. No hooks, MCP server, app references, private skills, or project state.
- Licenses: Apache-2.0 framework; designated original MIT-0 templates. Generated
  applications receive no imposed framework license or application copyright owner.

The ignored build output is produced locally from committed sources; it is not a
GitHub release asset or a published plugin. Rebuild into a new directory and compare
the checksum before reviewing or submitting an exact candidate.

## Exercised paths

The macOS Codex CLI `0.159.0-alpha.12.1` accepted the local marketplace, installed
`noetloom@noetloom-local-review`, and reported it enabled. An initial package was used
for the agent exercise below. After documentation, closure-validation, and shared-logo refinements,
the final ZIP above was rebuilt, installed again, and every installed payload hash
was compared to `bundle.json`. Fresh bootstrap and generated helper checks passed.
The temporary plugin installation and marketplace registration were removed afterward;
the generated project still passed its local check. Other installations were untouched.

The listing uses the current faceted diamond logo from ShardLoom's published GitHub,
with source provenance in [assets/README.md](../assets/README.md). The SVG has explicit
128 × 128 dimensions; geometry and colors match the source. Its installed bytes were
included in the final payload comparison.

| Exercise | Observed result |
| --- | --- |
| Installed-package creation | An isolated native Codex agent read the installed bootstrap skill/resources and created a compact CSV duplicate-ID project. Its real CLI and four behavioral tests passed; P-001 completed with evidence `check-e49eb7a2fdf841e6ace32c243e57d293`. |
| Interrupted intake | A simulated correction required trimming and lowercase comparison while retaining total row count and excluding blank IDs from duplicates. A separate dashboard question and pause were recorded before reconciliation. |
| Fresh continuation | Another native agent received only the local project and “Continue.” It read pending receipts, recorded resume, reopened P-001, updated owners/code/tests, answered the question without expanding scope, and completed cycle 2 with evidence `check-ecf60149d59442eab6dd53c1ea4d6b87`. |
| Actual result | Padded mixed-case IDs produced `{"duplicate_ids": ["x"], "total_rows": 2}`. The four-test suite and local framework check passed. Input remained unchanged. |
| Package independence | Automated tests extract the ZIP, bootstrap, remove the disposable extraction, and reconcile feedback in separate isolated Python processes using only generated files. Native generated-project checking also succeeded after uninstall. |
| Reproducibility and scope | Automated tests compare complete ZIP bytes, canonical skill bytes, source hashes, manifest resources, and absence of hooks/MCP/project records. Existing build directories cannot be overwritten. |

The native exercise's project ID is `ddba0e16-54ed-4c50-b27d-7152be496960`.
Its final application SHA-256 is `22b90a6dcf6974666f78269d04fba9111ed25bd072711a9ccadf92b9622b9c23`;
its test source SHA-256 is `37aa484c0cfaeb60bf49cc6ef78f143f45e3fae463033b491e20279a1b7845ea`.
These identify a disposable local exercise, not an independently replayable public
benchmark. The maintained repository examples and automated tests provide repeatable
behavioral checks. The exercise exposed confusion between the kit command and the
copied helper; generated instructions now state the correct local command explicitly.

## Suggested review prompts

1. “Create a local project for an offline reading list, with no accounts, and start
   implementing.” Expect workspace selection, local framework, actual functionality,
   tests, and current evidence; no application under the plugin installation.
2. “Actually, this needs to work offline; don't add authentication yet.” Expect owner,
   plan, and validation reconciliation and affected reopening, not acknowledgement alone.
3. “Could multiple users share it eventually?” Expect an answer without silently adding
   authentication, sync, or tenancy work.
4. “Pause here.” Then, in a fresh session, “Continue.” Expect durable pause and explicit
   resumption, with pending corrections processed before the old checkpoint.
5. Ask to create files in a host without workspace/Python tools. Expect an accurate
   limitation, not fabricated files or evidence. This host-limitation scenario has not
   been executed on web/mobile in this task.

## External checks still required before publication

No ChatGPT Directory upload, automated submission scan, verified-developer selection,
review approval, or publication occurred. Native Claude discovery, automatic OpenAI
plugin selection, and ChatGPT web/mobile execution were not exercised. Confirm current
eligibility and listing/support/privacy requirements through the official sources in
[plugin.md](plugin.md) before any later authorized submission. Local installation is
evidence of one host path; it is not a guarantee of Directory eligibility or all-host
tool availability.
