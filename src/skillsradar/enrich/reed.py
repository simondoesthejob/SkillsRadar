"""Fetch the full description of Reed postings and cache it in S3.

Reed's search results carry a description cut to about 450 characters; the full text needs one
call per job to `/jobs/{id}`. Each posting is fetched once: the response is stored as
`enriched/reed/<id>.json.gz` in the raw bucket and the curation Lambda picks it up from there.
A posting that has since been removed (HTTP 404 or 410) is stored as a "gone" marker so it is not
retried every day.

Run it by hand or from a schedule; each run fetches at most `max_new` postings so a large backlog
is cleared over several runs rather than one very long one.
"""

from __future__ import annotations

import gzip
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from skillsradar.http import HttpError, get_json
from skillsradar.sources.reed import basic_auth_header
from skillsradar.storage import ObjectStore, enriched_key, enriched_prefix

DETAIL_URL = "https://www.reed.co.uk/api/1.0/jobs"
SOURCE = "reed"
_DT_IN_KEY = re.compile(r"/dt=(\d{4}-\d{2}-\d{2})/")
_GONE_STATUS = {404, 410}
_STOP_STATUS = {401, 403, 429}  # bad key or rate limited: more calls would only make it worse
_MAX_CONSECUTIVE_FAILURES = 5


@dataclass(frozen=True)
class EnrichSettings:
    raw_bucket: str
    reed_secret_arn: str = ""
    max_new: int = 300
    lookback_days: int = 3
    request_interval: float = 1.0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> EnrichSettings:
        import os

        env = dict(os.environ) if env is None else env
        return cls(
            raw_bucket=env["RAW_BUCKET"],
            reed_secret_arn=env.get("REED_SECRET_ARN", ""),
            max_new=int(env.get("MAX_NEW", "300")),
            lookback_days=int(env.get("LOOKBACK_DAYS", "3")),
            request_interval=float(env.get("REQUEST_INTERVAL_SECONDS", "1.0")),
        )


def raw_days(store: ObjectStore, bucket: str) -> list[str]:
    keys = store.list_keys(bucket, f"raw/source={SOURCE}/")
    return sorted({m.group(1) for k in keys if (m := _DT_IN_KEY.search(k))}, reverse=True)


def candidate_ids(store: ObjectStore, bucket: str, days: list[str]) -> list[str]:
    """Reed job IDs seen on the given days, newest day first, each once."""
    seen: dict[str, None] = {}
    for dt in days:
        prefix = f"raw/source={SOURCE}/dt={dt}/"
        for key in sorted(store.list_keys(bucket, prefix)):
            if not key.endswith(".jsonl.gz"):
                continue
            for line in gzip.decompress(store.read(bucket, key)).decode("utf-8").splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict) and record.get("source_id"):
                    seen.setdefault(str(record["source_id"]), None)
    return list(seen)


def run(
    event: dict[str, Any] | None,
    store: ObjectStore,
    settings: EnrichSettings,
    fetch_detail: Callable[[str], dict[str, Any]],
    now: datetime | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Event options: {"all": true} scan every day, {"lookback_days": n}, {"max_new": n}."""
    event = event or {}
    now = now or datetime.now(UTC)
    max_new = int(event.get("max_new", settings.max_new))
    days = raw_days(store, settings.raw_bucket)
    if not event.get("all"):
        days = days[: int(event.get("lookback_days", settings.lookback_days))]

    ids = candidate_ids(store, settings.raw_bucket, days)
    cached = set(store.list_keys(settings.raw_bucket, enriched_prefix(SOURCE)))
    todo = [i for i in ids if enriched_key(SOURCE, i) not in cached]

    summary: dict[str, Any] = {
        "days_scanned": days,
        "candidate_ids": len(ids),
        "already_enriched": len(ids) - len(todo),
        "fetched": 0,
        "gone": 0,
        "failed": 0,
        "stopped_reason": None,
        "detail_keys": None,
    }
    consecutive_failures = 0
    attempted = 0
    for job_id in todo[:max_new]:
        if attempted:
            sleep(settings.request_interval)
        attempted += 1
        try:
            detail = fetch_detail(job_id)
            summary["fetched"] += 1
            if summary["detail_keys"] is None and isinstance(detail, dict):
                summary["detail_keys"] = sorted(detail)
        except HttpError as exc:
            if exc.status in _GONE_STATUS:
                detail = {"jobId": job_id, "gone": True}
                summary["gone"] += 1
            elif exc.status in _STOP_STATUS:
                summary["stopped_reason"] = f"HTTP {exc.status}"
                break
            else:
                summary["failed"] += 1
                consecutive_failures += 1
                if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                    summary["stopped_reason"] = "too many consecutive failures"
                    break
                continue
        consecutive_failures = 0
        detail["fetched_at"] = now.isoformat()
        store.write(
            settings.raw_bucket,
            enriched_key(SOURCE, job_id),
            gzip.compress(json.dumps(detail, ensure_ascii=False).encode("utf-8")),
        )
    summary["remaining"] = len(todo) - summary["fetched"] - summary["gone"]
    return summary


def make_fetcher(api_key: str) -> Callable[[str], dict[str, Any]]:
    headers = basic_auth_header(api_key)

    def fetch(job_id: str) -> dict[str, Any]:
        payload = get_json(f"{DETAIL_URL}/{job_id}", headers=headers)
        if not isinstance(payload, dict):
            raise HttpError("unexpected response shape")
        return payload

    return fetch
