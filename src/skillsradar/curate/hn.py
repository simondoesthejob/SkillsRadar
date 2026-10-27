"""Hacker News "Who is hiring?" posts start with a header line, by convention:

    Company | Role | Location | REMOTE | Visa | ...

The segment order varies, so location is found by elimination: the first short segment that is
not the company, a remote/onsite marker, a contract type, a salary or a job title. It is a
heuristic; the share of posts where it finds a location is reported in the quality stats.
"""

from __future__ import annotations

import re

_REMOTE = re.compile(r"^(?:fully\s+|100%\s+)?(?:remote|wfh)\b(?P<rest>.*)$", re.IGNORECASE)
_REMOTE_PLACE = re.compile(r"\(([^)]+)\)")
_ONSITE = re.compile(r"^(?:on[- ]?site|in[- ]office|office)\b", re.IGNORECASE)
_NOT_PLACE = re.compile(
    r"(?:\bvisa\b|\brelocat|full[- ]?time|part[- ]?time|\bcontract\b|\bintern|\bequity\b|"
    r"\bhiring\b|https?://|www\.|[£$€]|\d|[&/+@]|"
    # several roles or a vague scope rather than a place
    r"\b(?:multiple|various|several|many|roles?|positions?|openings?|vacanc\w+|listed|worldwide|"
    r"global|anywhere)\b|"
    # work arrangement, eligibility and domain names
    r"\bhybrid\b|\bcitizen\w*|\brequired\b|\beligib\w+|\bauthori[sz]\w+|\bsponsor\w*|"
    r"\bclearance\b|\.(?:com|io|ai|co|org|net|dev|app|uk|us|xyz)\b|"
    # time zones
    r"\btime\s?zones?\b|\btime\b|\b(?:gmt|utc|cet|cest|eet|bst|[ecmp][sd]t)\b|"
    # teams, products and technologies
    r"\b(?:tooling|platform|infrastructure|devex|genai|ai|ml|team|engineering|software|"
    r"product|data|security)\b)",
    re.IGNORECASE,
)
_ROLE = re.compile(
    r"\b(?:engineer|developer|scientist|manager|designer|analyst|architect|researcher|"
    r"lead|head of|director|cto|sre|devops|programmer|consultant|specialist|founder)s?\b",
    re.IGNORECASE,
)
_MAX_PLACE_CHARS = 60
_MAX_PLACE_WORDS = 6


def _looks_like_place(segment: str) -> bool:
    return (
        len(segment) <= _MAX_PLACE_CHARS
        and len(segment.split()) <= _MAX_PLACE_WORDS
        and not _NOT_PLACE.search(segment)
        and not _ROLE.search(segment)
    )


def parse_header(first_line: str) -> tuple[str | None, bool | None]:
    """Return (location, remote) found in a header line. Either may be None."""
    segments = [s.strip() for s in first_line.split("|")]
    location: str | None = None
    remote: bool | None = None

    for segment in segments[1:]:
        if not segment:
            continue
        match = _REMOTE.match(segment)
        if match:
            remote = True
            place = _REMOTE_PLACE.search(match.group("rest"))
            if place and location is None:
                candidate = place.group(1).strip()
                if candidate and _looks_like_place(candidate):
                    location = candidate
            continue
        if _ONSITE.match(segment):
            if remote is None:
                remote = False
            continue
        if location is not None:
            continue
        if _looks_like_place(segment):
            location = segment
    return location, remote
