"""Runtime settings, read from environment variables (set by Terraform on the Lambda)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_QUERIES = (
    "data scientist",
    "machine learning engineer",
    "data engineer",
    "software engineer",
    "senior software engineer",
    "data journalist",
)


def _queries(raw: str) -> tuple[str, ...]:
    return tuple(q.strip() for q in raw.split(",") if q.strip()) or DEFAULT_QUERIES


@dataclass(frozen=True)
class Settings:
    raw_bucket: str
    adzuna_secret_arn: str = ""
    adzuna_country: str = "gb"
    adzuna_queries: tuple[str, ...] = DEFAULT_QUERIES
    adzuna_pages_per_query: int = 2
    adzuna_results_per_page: int = 50
    reed_secret_arn: str = ""
    reed_queries: tuple[str, ...] = DEFAULT_QUERIES
    reed_location: str = ""  # empty means UK-wide
    reed_pages_per_query: int = 2
    reed_results_per_page: int = 100
    # Adzuna's default limit is 25 calls/minute; 2.5s spacing keeps us well inside it and is
    # a polite default for Reed too (check Reed's own terms when you register your key).
    request_interval_seconds: float = 2.5
    hn_threads: int = 1

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        return cls(
            raw_bucket=env["RAW_BUCKET"],
            adzuna_secret_arn=env.get("ADZUNA_SECRET_ARN", ""),
            adzuna_country=env.get("ADZUNA_COUNTRY", "gb"),
            adzuna_queries=_queries(env.get("ADZUNA_QUERIES", "")),
            adzuna_pages_per_query=int(env.get("ADZUNA_PAGES_PER_QUERY", "2")),
            adzuna_results_per_page=int(env.get("ADZUNA_RESULTS_PER_PAGE", "50")),
            reed_secret_arn=env.get("REED_SECRET_ARN", ""),
            reed_queries=_queries(env.get("REED_QUERIES", "")),
            reed_location=env.get("REED_LOCATION", ""),
            reed_pages_per_query=int(env.get("REED_PAGES_PER_QUERY", "2")),
            reed_results_per_page=int(env.get("REED_RESULTS_PER_PAGE", "100")),
            request_interval_seconds=float(env.get("REQUEST_INTERVAL_SECONDS", "2.5")),
            hn_threads=int(env.get("HN_THREADS", "1")),
        )
