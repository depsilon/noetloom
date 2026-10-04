# Readable autonomous-development exercise

Observed October 4, 2026 in a native Codex session. This record describes what ran;
it is not a benchmark of universal agent capability or proof that Noetloom caused an
improvement over another method. The application used ordinary Python and SQLite tools.

## Initial conditions

The initial application directory contained only a ToolShelf brief, the readable
operating method, and reference licenses. There was no application, prepared phase
plan, helper, native skill directory, or copied solution. The brief asked for an offline
tool-library CLI with catalog, lending, returns/history, explicit-date overdue reporting,
CSV preview and atomic import, export/recovery, persistence, tests and usage instructions.
Dashboard, authentication, cloud sync, web UI and notifications were deferred.

The first native agent received the directory, brief and method, with instructions to
derive the project guidance and work, implement and verify, and continue across phases.
It was instructed to use only this directory and ordinary application tools, with no
Noetloom commands, original conversation, private skills, native discovery, network,
third-party installation, model API, remote effects or further agents. This was an
instructional isolation exercise on a shared machine, not an OS sandbox.

## Observed sequence

1. The agent derived [three concrete phases](initial-plan.md): durable catalog/CLI;
   lending, returns and overdue reporting; safe transfer, recovery and integrated delivery.
   It wrote local project contracts and a routing entrypoint using ordinary Markdown.
2. Catalog behavior passed nine tests and actual separate-process CLI checks. Duplicate
   and invalid requests left stored bytes unchanged. The agent reported the milestone
   and advanced into lending without waiting for another instruction. It diagnosed an
   unsuitable default Python 3.9 and used the already installed Python 3.13.
3. One simulated mid-project correction required trimmed, case-insensitive asset IDs
   across commands and CSV, with atomic rejection of normalized duplicates. Existing
   dashboard/authentication/sync deferrals remained in force.
4. The agent recorded the correction in project contracts, guidance, plan and progress,
   reopened affected work, and distinguished capture from source implementation.
   At 19:11 UTC it was interrupted. [The saved progress](interrupted-progress.md) and
   [plan](interrupted-plan.md) are historical snapshots, not additional active queues.
   Source inspection confirmed normalization was not implemented at that interruption.
5. A new native agent with no originating conversation received only the directory and
   an instruction to continue from its local entrypoint. The prompt did not repeat the
   requirements, correction, plan or next action. It recovered those from local files,
   implemented normalization and existing-data compatibility, then lending, returns,
   history and overdue reporting. Seventeen tests passed, including competing CLI loans.
   It proceeded to CSV transfer, recovery and review without further steering.

6. The fresh agent completed all three phases: 36 tests, compileall, the complete real
   CLI journey, recovery/Unicode round-trip, and 18 README CLI examples passed. It left
   completion, limits and source identities in the ordinary local owners and reported
   the result. No further user task selection or implementation direction was supplied.
7. Primary acceptance review reproduced one missed correction edge: IDs padded with
   tabs/newlines failed before trimming. A regression failed, then the shared boundary
   was repaired. The maintained example passes 39 tests and a rerun of the full journey.
   Windows symlink creation was isolated as a platform-dependent test. This additional
   repair is distinguished from the fresh agent's original 36-test result.

The working application, its derived plan, readable guidance and retained artifacts are
in [examples/tool-shelf](../../../examples/tool-shelf/README.md). Current acceptance is
in [its validation record](../../../examples/tool-shelf/VALIDATION.md). The native agent's
original checksum list and all historical transcripts remain preserved. The primary's
[review patch](review.patch) records integration changes to source, tests and guidance.
[Source fingerprints](source-sha256.txt) bind the maintained files and snapshots to this
observation. The parent suite runs the actual application tests with ordinary Python.

## Proof boundary

The milestone and interruption notifications were test instrumentation, not user approval
gates. There was one substantive steering message. The local plan and application tools
carried the continuation; workflow records were ordinary Markdown. An active Codex host
ran both sessions. Human execution, other agent hosts, automatic skill selection, unattended
background operation, deployment and Directory publication were not exercised.

The exact guide snapshot remains with the example for audit. Its optional helper-reference
link refers to material in the source distribution, which this guide-only exercise did not
need or provide. Historical snapshots and source hashes can detect changes; they do not
independently replay the agent or authenticate the observation. Application tests exercise
the resulting behavior separately.
