"""Publish completed local files without replacing an existing destination."""

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

from .domain import ToolShelfError


@contextmanager
def new_file(destination: str | Path):
    path = Path(destination)
    if path.exists() or path.is_symlink():
        raise ToolShelfError(f"Destination already exists: {path}")
    descriptor, name = tempfile.mkstemp(prefix=".toolshelf-", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        # A same-directory hard link publishes the finished file atomically and
        # fails if another process created the destination while we were writing.
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise ToolShelfError(f"Destination already exists: {path}; retry the request.") from None
    finally:
        temporary.unlink(missing_ok=True)
