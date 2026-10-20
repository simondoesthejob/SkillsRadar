"""Validation and small per-field rules."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

# Search snippets are cut at a fixed length by the APIs (observed in the data: Reed at 453
# characters, Adzuna at 500). A description at or beyond the limit, or ending in an ellipsis,
# is treated as truncated. Hacker News text is complete.
TRUNCATION_LIMITS = {"adzuna": 500, "reed": 450}
_ELLIPSES = ("...", "…")

_DATE_PREFIX = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def is_truncated(source: str, description: str) -> bool:
    limit = TRUNCATION_LIMITS.get(source)
    if limit is None:
        return False
    stripped = description.rstrip()
    return len(stripped) >= limit or stripped.endswith(_ELLIPSES)


def parse_posted_date(value: str | None) -> date | None:
    """Date part of an ISO 8601 string, or None if it is missing or not a real date."""
    if not value:
        return None
    match = _DATE_PREFIX.match(value)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def hard_failures(record: dict[str, Any], source: str) -> list[str]:
    """Reasons a record must be rejected (quarantined) rather than curated."""
    reasons: list[str] = []
    if not str(record.get("source_id") or "").strip():
        reasons.append("missing_source_id")
    if not str(record.get("title") or "").strip():
        reasons.append("missing_title")
    if not str(record.get("description") or "").strip():
        reasons.append("missing_description")
    if record.get("source") != source:
        reasons.append("source_mismatch")
    for field in ("salary_min", "salary_max"):
        value = record.get(field)
        if value is not None and (not isinstance(value, int | float) or value < 0):
            reasons.append(f"invalid_{field}")
    return reasons
