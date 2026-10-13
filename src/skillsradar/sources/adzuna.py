"""Adzuna API source (https://developer.adzuna.com).

Terms to respect (see docs/data-sources.md): default limits of 25 calls/minute, 250/day,
1,000/week and 2,500/month, and attribution to "The Adzuna API" wherever data is published.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any

from skillsradar.http import get_json
from skillsradar.models import JobPosting

BASE_URL = "https://api.adzuna.com/v1/api/jobs"


class AdzunaSource:
    name = "adzuna"

    def __init__(
        self,
        app_id: str,
        app_key: str,
        *,
        country: str = "gb",
        queries: tuple[str, ...],
        pages_per_query: int = 2,
        results_per_page: int = 50,
        request_interval: float = 2.5,
        fetch_json: Callable[..., Any] = get_json,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._app_id = app_id
        self._app_key = app_key
        self._country = country
        self._queries = queries
        self._pages = pages_per_query
        self._per_page = results_per_page
        self._interval = request_interval
        self._fetch_json = fetch_json
        self._sleep = sleep
        self.requests_made = 0

    def fetch(self) -> Iterator[JobPosting]:
        for query in self._queries:
            for page in range(1, self._pages + 1):
                if self.requests_made:
                    self._sleep(self._interval)
                payload = self._fetch_json(
                    f"{BASE_URL}/{self._country}/search/{page}",
                    {
                        "app_id": self._app_id,
                        "app_key": self._app_key,
                        "results_per_page": self._per_page,
                        "what": query,
                        "sort_by": "date",
                        "content-type": "application/json",
                    },
                )
                self.requests_made += 1
                results = payload.get("results", [])
                for result in results:
                    yield self.parse(result)
                if len(results) < self._per_page:
                    break  # last page for this query

    @staticmethod
    def parse(result: dict[str, Any]) -> JobPosting:
        return JobPosting(
            source="adzuna",
            source_id=str(result["id"]),
            title=result.get("title", "").strip(),
            company=(result.get("company") or {}).get("display_name"),
            location=(result.get("location") or {}).get("display_name"),
            description=result.get("description", ""),
            url=result.get("redirect_url"),
            posted_at=result.get("created"),
            salary_min=result.get("salary_min"),
            salary_max=result.get("salary_max"),
            salary_predicted=str(result.get("salary_is_predicted", "0")) == "1",
            category=(result.get("category") or {}).get("label"),
            contract_type=result.get("contract_type"),
        )
