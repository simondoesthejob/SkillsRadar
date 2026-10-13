"""Ingestion Lambda: pull postings from each source and write gzipped JSONL to the raw bucket.

Objects are Hive-partitioned (`source=.../dt=YYYY-MM-DD/`) so Glue and Athena can prune by
source and day. Re-runs may produce duplicates; downstream steps dedupe on `dedupe_key`.
Adzuna also aggregates many of the same vacancies as Reed, so cross-source duplicates are
expected and are resolved in the curated layer, not here.
"""

from __future__ import annotations

import gzip
import json
import logging
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from typing import Any

from skillsradar.config import Settings
from skillsradar.models import JobPosting
from skillsradar.sources import JobSource
from skillsradar.sources.adzuna import AdzunaSource
from skillsradar.sources.hn_hiring import HnWhoIsHiring
from skillsradar.sources.reed import ReedSource

log = logging.getLogger()
log.setLevel(logging.INFO)

PutObject = Callable[[str, str, bytes], None]
ALL_SOURCES = ("adzuna", "reed", "hn_hiring")


def object_key(source: str, now: datetime) -> str:
    return f"raw/source={source}/dt={now:%Y-%m-%d}/run-{now:%H%M%S}.jsonl.gz"


def encode_jsonl_gz(postings: Iterable[JobPosting], ingested_at: datetime) -> tuple[bytes, int]:
    lines = [json.dumps(p.to_record(ingested_at), ensure_ascii=False) for p in postings]
    return gzip.compress(("\n".join(lines) + "\n").encode("utf-8")), len(lines)


def run(
    sources: Iterable[JobSource],
    bucket: str,
    put_object: PutObject,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run each source independently so one failing source cannot lose the others' data."""
    now = now or datetime.now(UTC)
    summary: dict[str, Any] = {"written": {}, "errors": {}}
    for source in sources:
        try:
            body, count = encode_jsonl_gz(source.fetch(), now)
        except Exception as exc:  # noqa: BLE001 - isolate per-source failures
            log.exception("source %s failed", source.name)
            summary["errors"][source.name] = str(exc)
            continue
        if count == 0:
            summary["written"][source.name] = 0
            continue
        put_object(bucket, object_key(source.name, now), body)
        summary["written"][source.name] = count
        log.info("source %s wrote %d postings", source.name, count)
    return summary


class UnavailableSource:
    """Stands in for a source that could not be constructed (e.g. its secret is missing).

    Failing at fetch time keeps the error inside `run`'s per-source isolation instead of
    aborting the whole invocation.
    """

    def __init__(self, name: str, error: Exception) -> None:
        self.name = name
        self._error = error

    def fetch(self) -> Iterator[JobPosting]:
        raise RuntimeError(f"source unavailable: {self._error}") from self._error


def build_sources(
    settings: Settings, wanted: Iterable[str], secrets: Callable[[str], dict]
) -> Iterator[JobSource]:
    wanted = set(wanted)
    unknown = wanted - set(ALL_SOURCES)
    if unknown:
        raise ValueError(f"unknown sources requested: {sorted(unknown)}")

    if "adzuna" in wanted:
        try:
            creds = secrets(settings.adzuna_secret_arn)
            yield AdzunaSource(
                creds["app_id"],
                creds["app_key"],
                country=settings.adzuna_country,
                queries=settings.adzuna_queries,
                pages_per_query=settings.adzuna_pages_per_query,
                results_per_page=settings.adzuna_results_per_page,
                request_interval=settings.request_interval_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            yield UnavailableSource("adzuna", exc)
    if "reed" in wanted:
        try:
            creds = secrets(settings.reed_secret_arn)
            yield ReedSource(
                creds["api_key"],
                queries=settings.reed_queries,
                location=settings.reed_location,
                pages_per_query=settings.reed_pages_per_query,
                results_per_page=settings.reed_results_per_page,
                request_interval=settings.request_interval_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            yield UnavailableSource("reed", exc)
    if "hn_hiring" in wanted:
        yield HnWhoIsHiring(threads=settings.hn_threads)


def lambda_handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    import boto3  # imported lazily: provided by the Lambda runtime, optional for unit tests

    settings = Settings.from_env()
    s3 = boto3.client("s3")
    secrets_client = boto3.client("secretsmanager")

    def get_secret(arn: str) -> dict:
        return json.loads(secrets_client.get_secret_value(SecretId=arn)["SecretString"])

    def put_object(bucket: str, key: str, body: bytes) -> None:
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentEncoding="gzip")

    wanted = (event or {}).get("sources", list(ALL_SOURCES))
    summary = run(build_sources(settings, wanted, get_secret), settings.raw_bucket, put_object)
    if summary["errors"]:
        # Raise after writing what we have so the failure reaches the DLQ and alarms.
        raise RuntimeError(f"ingestion errors: {summary['errors']}")
    return summary
