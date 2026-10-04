"""Source-checkout entrypoint. Project operations live in the copied standalone helper."""
import argparse
import json
from pathlib import Path
import sys

from .bootstrap import DOMAINS, bootstrap
from .runtime import helper


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"status", "check"}:
        return helper.main(args, Path.cwd())
    p = argparse.ArgumentParser(description="Optional helper profile for Noetloom's readable autonomous development method")
    sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("bootstrap")
    b.add_argument("target")
    b.add_argument("--name", required=True)
    b.add_argument("--prompt", required=True)
    b.add_argument("--domain", choices=DOMAINS, default="utility")
    b.add_argument("--adopt", action="store_true")
    b.add_argument("--compact", action="store_true")
    b.add_argument("--docs-dir", default="docs")
    b.add_argument("--example", action="store_true", help="Maintainer only: permit examples/<name> inside this checkout")
    sub.add_parser("status", help="Read this project's durable work state")
    sub.add_parser("check", help="Check this project's framework and current evidence")
    parsed = p.parse_args(args)
    try:
        values = vars(parsed)
        values.pop("command")
        result = bootstrap(**values)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (helper.FrameworkError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
