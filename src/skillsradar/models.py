"""Canonical record shared by every job source."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class JobPosting:
    source: str
    source_id: str
    title: str
    company: str | None
    location: str | None
    description: str
    url: str | None
    posted_at: str | None  # ISO 8601, as provided by the source
    salary_min: float | None = None
    salary_max: float | None = None
    salary_predicted: bool = False
    category: str | None = None
    contract_type: str | None = None

    @property
    def dedupe_key(self) -> str:
        return f"{self.source}:{self.source_id}"

    def to_record(self, ingested_at: datetime) -> dict:
        record = asdict(self)
        record["dedupe_key"] = self.dedupe_key
        record["ingested_at"] = ingested_at.isoformat()
        return record
