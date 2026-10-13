"""Job data sources. Each yields `JobPosting` records."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from skillsradar.models import JobPosting


class JobSource(Protocol):
    name: str

    def fetch(self) -> Iterator[JobPosting]: ...
