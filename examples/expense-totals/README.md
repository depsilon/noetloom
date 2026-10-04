# Expense totals

Run `python3 expense_totals.py INPUT.csv [--category CATEGORY]` with a UTF-8 CSV containing exactly
`category` and `amount` columns, in either order. Each row needs a nonblank category
and a finite amount with at most two decimal places; negative amounts are refunds.

The command prints sorted JSON category totals as two-decimal strings. A CSV containing
only the header prints `{}`. `--category` limits the output to one category and returns
`{}` when that category is absent; every row is still validated. Invalid input produces
an error on stderr and exits nonzero. The utility is local and offline; shared totals,
databases, and authentication are deferred until explicitly requested. The tool uses
only Python's standard library.
