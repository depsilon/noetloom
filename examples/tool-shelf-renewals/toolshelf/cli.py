"""Volunteer-facing command boundary."""

import argparse
import csv
from datetime import date
import sqlite3
import sys

from .domain import ToolShelfError, asset_identity
from .storage import Store
from .transfer import INVENTORY_COLUMNS, LOAN_COLUMNS, RENEWAL_COLUMNS, apply_import, export_archive, preview_import


def table(rows: list[dict], columns: tuple[str, ...]) -> None:
    writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    writer.writerow(columns)
    writer.writerows([row[column] for column in columns] for row in rows)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="toolshelf", description="ToolShelf — an offline neighborhood tool library.")
    result.add_argument("--db", default="toolshelf.sqlite3", help="SQLite file (default: ./toolshelf.sqlite3)")
    commands = result.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="Add a uniquely identified tool")
    add.add_argument("asset_id")
    add.add_argument("name")
    inventory = commands.add_parser("inventory", help="List tools and current availability")
    inventory.add_argument("--available", action="store_true", help="Only show available tools")
    lend = commands.add_parser("lend", help="Lend an available tool")
    lend.add_argument("asset_id")
    lend.add_argument("borrower")
    lend.add_argument("--due", required=True, help="Due date, YYYY-MM-DD")
    lend.add_argument("--on", default=None, help="Lending date, YYYY-MM-DD (default: today)")
    renew = commands.add_parser("renew", help="Extend an active loan and retain its renewal history")
    renew.add_argument("asset_id")
    renew.add_argument("--due", required=True, help="New due date, YYYY-MM-DD (later than current due date)")
    renew.add_argument("--on", required=True, help="Renewal date, YYYY-MM-DD")
    renewals = commands.add_parser("renewals", help="List all loan renewal history")
    renewals.add_argument("--asset", help="Only show history for this asset ID")
    returning = commands.add_parser("return", help="Close the active loan for a tool")
    returning.add_argument("asset_id")
    returning.add_argument("--on", default=None, help="Return date, YYYY-MM-DD (default: today)")
    loans = commands.add_parser("loans", help="List all loan history")
    loans.add_argument("--active", action="store_true", help="Only show active loans")
    overdue = commands.add_parser("overdue", help="List current loans overdue on an explicit date")
    overdue.add_argument("--as-of", required=True, help="Query date, YYYY-MM-DD")
    importing = commands.add_parser("import", help="Preview CSV, or apply an unchanged confirmed preview")
    importing.add_argument("csv_file", help="UTF-8 CSV with asset_id,name headers")
    importing.add_argument("--confirm", metavar="TOKEN", help="Token printed by the unchanged preview")
    exporting = commands.add_parser("export", help="Export catalog, inventory, loans, renewals and database to a new ZIP")
    exporting.add_argument("archive", help="New ZIP file; never overwrites an existing path")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    store = Store(args.db)
    try:
        if args.command == "add":
            store.add(args.asset_id, args.name)
            print(f"Added {asset_identity(args.asset_id)}.")
        elif args.command == "inventory":
            table(store.inventory(available_only=args.available), INVENTORY_COLUMNS)
        elif args.command == "lend":
            on = args.on if args.on is not None else date.today().isoformat()
            loan_id = store.lend(args.asset_id, args.borrower, args.due, on)
            print(f"Loan {loan_id}: lent {asset_identity(args.asset_id)}.")
        elif args.command == "return":
            on = args.on if args.on is not None else date.today().isoformat()
            loan_id = store.return_tool(args.asset_id, on)
            print(f"Loan {loan_id}: returned {asset_identity(args.asset_id)}.")
        elif args.command == "renew":
            renewal_id = store.renew(args.asset_id, args.due, args.on)
            print(f"Renewal {renewal_id}: renewed {asset_identity(args.asset_id)} until {args.due}.")
        elif args.command == "renewals":
            table(store.renewals(asset_id=args.asset), RENEWAL_COLUMNS)
        elif args.command == "loans":
            table(store.loans(active_only=args.active), LOAN_COLUMNS)
        elif args.command == "overdue":
            table(store.loans(as_of=args.as_of), LOAN_COLUMNS)
        elif args.command == "import":
            if args.confirm is None:
                batch, token = preview_import(store, args.csv_file)
                table([{"line": row.line, "asset_id": row.asset_id, "name": row.name} for row in batch.rows],
                      ("line", "asset_id", "name"))
                print(f"Preview: {len(batch.rows)} tools; no data written.")
                print(f"Preview token: {token}")
                print("To apply this unchanged file and catalog, repeat import with --confirm TOKEN.")
            else:
                count = apply_import(store, args.csv_file, args.confirm)
                print(f"Imported {count} tools.")
        elif args.command == "export":
            export_archive(store, args.archive)
            print(f"Exported to {args.archive}.")
    except ToolShelfError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError) as error:
        print(f"Error: local file/database operation failed: {error}", file=sys.stderr)
        return 1
    return 0
