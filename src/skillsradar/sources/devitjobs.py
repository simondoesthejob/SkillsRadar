"""DevITjobs UK: the site's public XML job feed (https://devitjobs.uk/job_feed.xml).

One unauthenticated GET returns every live tech posting (about 1,600 at the time of writing), each
with a full HTML description, so there is no paging and no enrichment step. We fetch it once a day.
The site's robots.txt does not restrict the feed. Postings link back to devitjobs.uk and should be
shown as "via DevITjobs" wherever they appear (docs/data-sources.md).

Quirks of the feed, all handled here:

* Each `<id>` ends in a week tag (`-W44`) that changes every week, so the same posting would look
  new every Monday. The stable part is the Mongo-style hex id before it.
* About a quarter of the postings (agencies re-posting from other boards) have the salary
  "£? - ? per year": no salary at all, not a number to parse.
* Dates are day-first with dots (04.10.2023).
* `<location>` is a messy street-level string; `<city>` is clean, so that is the location we keep.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from datetime import datetime

from skillsradar.http import HttpError, get_bytes
from skillsradar.models import JobPosting

FEED_URL = "https://devitjobs.uk/job_feed.xml"
MAX_FEED_BYTES = 40 * 1024 * 1024  # the feed is about 6 MB; refuse anything wildly larger

_WEEK_TAG = re.compile(r"-W\d+$")
_NUMBER = r"(\d[\d,]*(?:\.\d+)?)"
_SALARY = re.compile(rf"£\s*{_NUMBER}(?:\s*-\s*£?\s*{_NUMBER})?")


def stable_id(feed_id: str) -> str:
    """The feed id without its weekly `-W44` tag."""
    return _WEEK_TAG.sub("", feed_id.strip())


def parse_pubdate(raw: str | None) -> str | None:
    """Day-first dotted dates (04.10.2023) to ISO; the raw text if unrecognised."""
    if not raw or not raw.strip():
        return None
    try:
        return datetime.strptime(raw.strip(), "%d.%m.%Y").date().isoformat()
    except ValueError:
        return raw.strip()


def parse_salary(raw: str | None) -> tuple[float | None, float | None]:
    """(min, max) from "£35,000 - 40,000 per year"; "£? - ? per year" has none: (None, None)."""
    match = _SALARY.search(raw or "")
    if not match:
        return None, None
    low = float(match.group(1).replace(",", ""))
    high = float(match.group(2).replace(",", "")) if match.group(2) else low
    return low, high


def _text(job: ET.Element, tag: str) -> str:
    return (job.findtext(tag) or "").strip()


def refuse_unsafe_xml(data: bytes) -> None:
    """A job feed has no reason to declare entities; refuse one that does (expansion attacks)."""
    head = data[:8192].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
        raise ValueError("feed contains a DOCTYPE or ENTITY declaration; refusing to parse it")


class DevITjobsSource:
    name = "devitjobs"

    def __init__(
        self,
        feed_url: str = FEED_URL,
        *,
        fetch_bytes: Callable[..., bytes] = get_bytes,
    ) -> None:
        self._url = feed_url
        self._fetch_bytes = fetch_bytes

    def fetch(self) -> Iterator[JobPosting]:
        data = self._fetch_bytes(
            self._url,
            headers={"Accept": "application/xml"},
            timeout=60.0,
            max_bytes=MAX_FEED_BYTES,
        )
        refuse_unsafe_xml(data)
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise HttpError(f"feed is not valid XML: {exc}") from exc
        if root.tag != "jobs":
            raise HttpError(f"unexpected feed root element <{root.tag}>")
        seen: set[str] = set()
        for job in root.findall("job"):
            posting = self.parse(job)
            if posting is None or posting.source_id in seen:
                continue
            seen.add(posting.source_id)
            yield posting

    @staticmethod
    def parse(job: ET.Element) -> JobPosting | None:
        feed_id = _text(job, "id") or job.get("id", "")
        title = _text(job, "title") or _text(job, "name")
        if not feed_id or not title:
            return None
        low, high = parse_salary(_text(job, "salary"))
        city = _text(job, "city")
        if not city:  # fall back to the last part of the street-level location
            parts = [p.strip() for p in _text(job, "location").split(",") if p.strip()]
            city = parts[-1] if parts else ""
        return JobPosting(
            source="devitjobs",
            source_id=stable_id(feed_id),
            title=title,
            company=_text(job, "company") or None,
            location=city or None,
            description=_text(job, "description"),  # HTML; converted to text when curated
            url=_text(job, "link") or _text(job, "url") or None,
            posted_at=parse_pubdate(_text(job, "pubdate")),
            salary_min=low,
            salary_max=high,
            category=None,
            contract_type=_text(job, "jobtype") or None,
        )
