# expense-totals

## Purpose

Build a Python standard-library CLI that totals CSV expenses by category. Input columns are category and amount; output stable JSON totals with two decimal places. Reject malformed or non-finite amounts with an error and nonzero exit. Allow negative refunds. No network services or authentication.

## Scope and authority

This is a maintained Noetloom example, originally built in an isolated disposable
workspace. Local implementation, correction, and tests are authorized for this example.
It does not grant authority to publish a user's data or deploy a service.

## Requirements and deferred scope

Exact sums must preserve cents when very large whole values and fractional amounts
are combined; digit counts alone must not cause silent context rounding.

Concrete acceptance: `python3 expense_totals.py INPUT.csv [--category CATEGORY]` reads
UTF-8 CSV with exactly the `category` and `amount` columns, in either order. Each data
row has exactly two fields, a nonblank category, and a finite decimal amount with at
most two fractional digits. Amounts are summed exactly, including negative refunds.
An optional category filter selects only the matching total; when absent from valid
input it prints `{}`. The command validates every row, including rows outside the
selected category. Success writes only JSON to stdout, with category keys in lexical
order and amount strings in fixed two decimal places; a header-only file prints `{}`.
Invalid or unreadable input writes an actionable error to stderr, exits nonzero, and
emits no partial stdout. The tool uses only the Python standard library and has no
network or authentication behavior.

Sharing totals among multiple people is deferred until explicitly requested. The
current utility is local and offline; databases and authentication are also deferred
until explicitly requested.

## Architecture

The user runs a single-file Python CLI, supplies the CSV path as a positional argument,
and may supply `--category CATEGORY`. `csv.reader` validates the exact header and row
widths; `Decimal` parses and sums base-10 amounts without binary floating-point drift.
Categories are trimmed at the edges and used as JSON keys. The command parses and
validates the entire input before applying the optional filter, so malformed rows in
unselected categories still fail. The complete result is assembled before printing so
input failures cannot leave partial output. JSON is UTF-8 text with two-space
indentation and a final newline. Input files are read only.

## Framework maintenance

This maintained example retains the optional Noetloom helper profile. The readable
`.noetloom/operating-model.md` is the complete development method; `.noetloom/helpers.md`
documents the profile's records and checks. The marked plan JSON is the representation
of the single project plan. This framework refresh changes no application requirements
or deferred scope.
