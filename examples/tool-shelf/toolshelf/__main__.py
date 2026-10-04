import sys

if sys.version_info < (3, 11):
    print("Error: ToolShelf requires Python 3.11+; try python3.13 on this machine.", file=sys.stderr)
    raise SystemExit(1)

from .cli import main

raise SystemExit(main())
