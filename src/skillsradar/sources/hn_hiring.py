"""Hacker News "Ask HN: Who is hiring?" threads via the public Algolia API (no key needed)."""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

from skillsradar.http import get_json
from skillsradar.models import JobPosting

API = "https://hn.algolia.com/api/v1"
THREAD_TITLE = re.compile(r"^Ask HN: Who is hiring\?", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_BREAK = re.compile(r"<(?:p|br)\s*/?>", re.IGNORECASE)


def html_to_text(raw: str) -> str:
    text = _BREAK.sub("\n", raw)
    text = _TAG.sub("", text)
    return html.unescape(text).strip()


class HnWhoIsHiring:
    name = "hn_hiring"

    def __init__(self, *, threads: int = 1, fetch_json: Callable[..., Any] = get_json) -> None:
        self._threads = threads
        self._fetch_json = fetch_json

    def fetch(self) -> Iterator[JobPosting]:
        search = self._fetch_json(
            f"{API}/search_by_date",
            {"tags": "story,author_whoishiring", "hitsPerPage": 10},
        )
        thread_ids = [
            hit["objectID"] for hit in search.get("hits", []) if THREAD_TITLE.match(hit["title"])
        ]
        for thread_id in thread_ids[: self._threads]:
            thread = self._fetch_json(f"{API}/items/{thread_id}")
            for comment in thread.get("children", []):
                posting = self.parse(comment)
                if posting is not None:
                    yield posting

    @staticmethod
    def parse(comment: dict[str, Any]) -> JobPosting | None:
        raw = comment.get("text")
        if not raw:  # deleted or dead comments carry no text
            return None
        text = html_to_text(raw)
        first_line = text.split("\n", 1)[0]
        segments = [s.strip() for s in first_line.split("|")]
        created = comment.get("created_at_i")
        posted_at = datetime.fromtimestamp(created, UTC).isoformat() if created else None
        return JobPosting(
            source="hn_hiring",
            source_id=str(comment["id"]),
            title=first_line[:200],
            company=segments[0] or None,
            location=None,  # free-text; extracted later in the NLP step
            description=text,
            url=f"https://news.ycombinator.com/item?id={comment['id']}",
            posted_at=posted_at,
        )
