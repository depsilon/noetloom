# Existing ToolShelf change objective

This directory contains a working ToolShelf application with a durable catalog,
lending/returns, overdue reports, CSV import and recovery export. Extend that application
for volunteers who need to renew an active loan without erasing its history. Preserve
the existing architecture where it serves the change, public behavior, saved data,
deferred scope and ordinary local-file workflow. Derive your own implementation phases
and guidance after inspecting the existing application; this brief supplies outcomes.

## Requested behavior

- A volunteer can run `renew ASSET_ID --due YYYY-MM-DD --on YYYY-MM-DD`. Both dates
  are explicit. A successful renewal extends the same active loan, preserving its ID,
  borrower and lending date. Existing trimmed/casefolded asset identity applies.
- The new due date must be strictly later than the current due date and no earlier than
  the renewal date. The renewal date must not precede lending or an earlier renewal on
  that loan. An overdue loan may be renewed under those rules. Unknown assets, assets
  without an active loan, malformed/empty dates, shorter/equal extensions and reversed
  chronology fail without changing saved bytes. Repeating an already applied extension
  is rejected. A return cannot precede the latest renewal, either.
- `renewals` shows all renewal history; `renewals --asset ASSET_ID` filters by normalized
  asset identity. Use the existing TSV report convention with columns, in this order:
  `renewal_id, loan_id, asset_id, old_due_on, new_due_on, renewed_on`.
  The history has stable distinct event IDs and is ordered by those IDs. Returning or
  borrowing an asset again retains its earlier loans and renewal history.
- Inventory, active loans and overdue reports use the current due date while preserving
  their existing columns and meanings. The overdue boundary remains exclusive.
  Competing commands must not lose history or produce conflicting due-date transitions.
- Existing owned version-1 and version-2 databases and prior recovery snapshots remain
  usable with their IDs and data preserved. Read-only commands, including renewal history,
  do not rewrite a saved database. Any necessary upgrade happens safely with a valid
  mutation; a rejected mutation leaves the original bytes unchanged. Existing rejection
  of foreign databases, unknown versions and legacy identity collisions remains.
- A new recovery ZIP preserves the existing entries and CSV headers, adds `renewals.csv`
  with the history columns above, and contains a consistent restorable database including
  all renewal events. Restored CLI queries match the exported snapshot. Export remains
  read-only for its source and cannot overwrite an existing destination.
- Catalog import/preview, duplicate detection and other unrelated behavior remain intact.
  A renewal alone does not stale a catalog preview. Continue using Python 3.11+ and the
  standard library, offline, without authentication, dashboards, cloud sync or services.

Completion means the integrated change works through actual CLI processes, relevant
regression checks and recovery examples pass, and usage/continuation files describe
the current application. Perform a final acceptance review against these requirements
as well as running your tests. Keep concise evidence of defects found during development
and any defects first found by that final review. Continue through the local completion
boundary without repeated task selection. Remote publication, installs and paid tools
are outside this application's authority.

