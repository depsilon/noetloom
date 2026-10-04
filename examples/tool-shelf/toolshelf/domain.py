"""Shared input contracts, independent of presentation and persistence."""

from datetime import date
import re
import unicodedata


class ToolShelfError(Exception):
    """A request or local data failure the volunteer can act on."""


def clean_text(value: str, label: str) -> str:
    if any(unicodedata.category(character) in {"Cc", "Cs", "Zl", "Zp"} for character in value):
        raise ToolShelfError(f"{label} must be a single line without control characters.")
    result = value.strip()
    if not result:
        raise ToolShelfError(f"{label} must not be empty.")
    return result


def asset_identity(value: str) -> str:
    """The one identity rule used for storage, lookup and transfer."""
    # Boundary whitespace is ignored; remaining internal controls are invalid.
    return clean_text(value.strip(), "Asset ID").casefold()


def calendar_date(value: str, label: str) -> str:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ToolShelfError(f"{label} must be a real date in YYYY-MM-DD format.")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ToolShelfError(f"{label} must be a real date in YYYY-MM-DD format.") from None
    return value
