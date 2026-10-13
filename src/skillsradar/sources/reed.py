"""Reed Jobseeker API source (https://www.reed.co.uk/developers/jobseeker).

Authentication is HTTP basic auth with the API key as the username and an empty password.
Search results carry a truncated description; full text needs one extra call per job via
`/jobs/{id}`, which is deliberately left to a later enrichment step so that only new postings
are fetched (see docs/architecture.md).
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

from skillsradar.http import get_json
from skillsradar.models import JobPosting

SEARCH_URL = "https://www.reed.co.uk/api/1.0/search"
MAX_RESULTS_PER_PAGE = 100  # documented maximum for resultsToTake


def basic_auth_header(api_key: str) -> dict[str, str]:
    token = base64.b64encode(f"{api_key}:".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def normalise_date(raw: str | None) -> str | None:
    """Reed dates are day-first (dd/mm/yyyy); fall back to the raw value if unrecognised."""
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


class ReedSource:
    name = "reed"

    def __init__(
        self,
        api_key: str,
        *,
        queries: tuple[str, ...],
        location: str = "",
        pages_per_query: int = 2,
        results_per_page: int = MAX_RESULTS_PER_PAGE,
        request_interval: float = 2.5,
        fetch_json: Callable[..., Any] = get_json,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._headers = basic_auth_header(api_key)
        self._queries = queries
        self._location = location
        self._pages = pages_per_query
        self._per_page = min(results_per_page, MAX_RESULTS_PER_PAGE)
        self._interval = request_interval
        self._fetch_json = fetch_json
        self._sleep = sleep
        self.requests_made = 0

    def fetch(self) -> Iterator[JobPosting]:
        for query in self._queries:
            for page in range(self._pages):
                if self.requests_made:
                    self._sleep(self._interval)
                params: dict[str, Any] = {
                    "keywords": query,
                    "resultsToTake": self._per_page,
                    "resultsToSkip": page * self._per_page,
                }
                if self._location:
                    params["locationName"] = self._location
                payload = self._fetch_json(SEARCH_URL, params, headers=self._headers)
                self.requests_made += 1
                results = payload.get("results", [])
                for result in results:
                    yield self.parse(result)
                if len(results) < self._per_page:
                    break  # last page for this query

    @staticmethod
    def parse(result: dict[str, Any]) -> JobPosting:
        return JobPosting(
            source="reed",
            source_id=str(result["jobId"]),
            title=(result.get("jobTitle") or "").strip(),
            company=result.get("employerName"),
            location=result.get("locationName"),
            description=result.get("jobDescription") or "",
            url=result.get("jobUrl"),
            posted_at=normalise_date(result.get("date")),
            salary_min=result.get("minimumSalary"),
            salary_max=result.get("maximumSalary"),
        )
