#!/usr/bin/env python3
"""Sum CSV expense amounts by category and print deterministic JSON."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation, localcontext
import json
import re
import sys
from pathlib import Path


AMOUNT_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)\Z")


class InputError(ValueError):
    """An input file does not match the supported CSV format."""


def parse_amount(text: str, line_number: int) -> Decimal:
    value = text.strip()
    if not AMOUNT_PATTERN.fullmatch(value):
        raise InputError(f"line {line_number}: invalid amount {text!r}")
    fractional = value.partition(".")[2]
    if len(fractional) > 2:
        raise InputError(f"line {line_number}: amount has more than 2 decimal places")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise InputError(f"line {line_number}: invalid amount {text!r}") from exc
    if not amount.is_finite():
        raise InputError(f"line {line_number}: amount must be finite")
    return amount


def total_file(path: Path) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    try:
        stream = path.open("r", encoding="utf-8", newline="")
    except OSError as exc:
        raise InputError(f"cannot open {path}: {exc.strerror or exc}") from exc
    try:
        with stream:
            rows = csv.reader(stream, strict=True)
            try:
                header = next(rows)
            except StopIteration as exc:
                raise InputError("input is empty; expected category,amount header") from exc
            if len(header) != 2 or set(header) != {"category", "amount"}:
                raise InputError("header must contain exactly category and amount")
            category_index = header.index("category")
            amount_index = header.index("amount")
            for line_number, row in enumerate(rows, start=2):
                if len(row) != 2:
                    raise InputError(f"line {line_number}: expected exactly 2 fields")
                category = row[category_index].strip()
                if not category:
                    raise InputError(f"line {line_number}: category must not be empty")
                amount = parse_amount(row[amount_index], line_number)
                current = totals.get(category, Decimal("0"))
                # Decimal arithmetic obeys the active context; grow it to retain every
                # input digit plus room for a carry when adding large exact amounts.
                # Reserve integer width, both fractional places, and a carry.
                # Digit counts alone miss scale alignment (10**100 + .01).
                precision = max(current.adjusted(), amount.adjusted(), 0) + 4
                with localcontext() as context:
                    context.prec = precision
                    totals[category] = current + amount
    except (OSError, UnicodeError, csv.Error) as exc:
        if isinstance(exc, csv.Error):
            raise InputError(f"malformed CSV: {exc}") from exc
        raise InputError(f"cannot read {path}: {exc}") from exc
    return totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="CSV file with category and amount columns")
    parser.add_argument("--category", help="show only this category's total")
    args = parser.parse_args(argv)
    try:
        totals = total_file(args.input)
    except InputError as exc:
        print(f"expense_totals: error: {exc}", file=sys.stderr)
        return 2
    if args.category is not None:
        category = args.category.strip()
        totals = {category: totals[category]} if category in totals else {}
    result = {}
    for category, amount in sorted(totals.items()):
        with localcontext() as context:
            context.prec = max(28, len(amount.as_tuple().digits) + 2)
            result[category] = format(amount.quantize(Decimal("0.01")), ".2f")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
