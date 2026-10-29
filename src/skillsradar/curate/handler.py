"""Curation Lambda: raw JSONL (one day, one source at a time) to curated Parquet.

Invoke with an optional event:
    {"dt": "2026-10-20"}                      one day
    {"dates": ["2026-10-19", "2026-10-20"]}   several days (backfill)
    {"all": true}                             every day present in the raw bucket
    {"sources": ["reed"]}                     limit to some sources
With no event it curates today (UTC), matching the `dt=` the ingestion Lambda writes.

Output is idempotent: a day and source always map to the same S3 keys, so re-running replaces
rather than duplicates. Rejected records go to quarantine/, and a small quality report goes to
quality/. If too many records are rejected, the function raises after writing everything so the
failure is visible.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from skillsradar.curate import metrics, parquet
from skillsradar.curate.pipeline import curate_day
from skillsradar.storage import ObjectStore, S3Store, enriched_key, enriched_prefix

log = logging.getLogger()
log.setLevel(logging.INFO)

ALL_SOURCES = ("adzuna", "reed", "hn_hiring")
METRICS_NAMESPACE = "SkillsRadar/Curation"
ENRICHED_SOURCES = ("reed",)  # sources whose full descriptions are fetched by the enrich Lambda
_DT_IN_KEY = re.compile(r"/dt=(\d{4}-\d{2}-\d{2})/")


@dataclass(frozen=True)
class CurateSettings:
    raw_bucket: str
    curated_bucket: str
    max_reject_ratio: float = 0.05

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> CurateSettings:
        import os

        env = dict(os.environ) if env is None else env
        return cls(
            raw_bucket=env["RAW_BUCKET"],
            curated_bucket=env["CURATED_BUCKET"],
            max_reject_ratio=float(env.get("MAX_REJECT_RATIO", "0.05")),
        )


def read_raw_records(store: ObjectStore, bucket: str, source: str, dt: str):
    """All records from every ingestion run of one source on one day, plus a bad-line count."""
    prefix = f"raw/source={source}/dt={dt}/"
    records: list[dict[str, Any]] = []
    bad_lines = 0
    keys = [k for k in store.list_keys(bucket, prefix) if k.endswith(".jsonl.gz")]
    for key in sorted(keys):
        body = gzip.decompress(store.read(bucket, key)).decode("utf-8")
        for line in body.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                bad_lines += 1
                continue
            if isinstance(record, dict):
                records.append(record)
            else:
                bad_lines += 1
    return records, bad_lines, len(keys)


def load_enriched(
    store: ObjectStore, bucket: str, source: str, ids: Iterable[str], workers: int = 16
) -> dict[str, dict[str, Any]]:
    """Cached full details (written by the enrich Lambda) for the given IDs, where they exist."""
    available = set(store.list_keys(bucket, enriched_prefix(source)))
    wanted = [i for i in ids if enriched_key(source, i) in available]

    def load(source_id: str) -> tuple[str, dict[str, Any] | None]:
        try:
            body = store.read(bucket, enriched_key(source, source_id))
            detail = json.loads(gzip.decompress(body))
            return source_id, detail if isinstance(detail, dict) else None
        except Exception:  # noqa: BLE001 - an unreadable cache entry just means "not enriched"
            log.warning("could not read enriched %s/%s", source, source_id)
            return source_id, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return {i: d for i, d in pool.map(load, wanted) if d}


def discover_dates(store: ObjectStore, bucket: str) -> list[str]:
    found = {m.group(1) for k in store.list_keys(bucket, "raw/") if (m := _DT_IN_KEY.search(k))}
    return sorted(found)


def resolve_dates(event: dict[str, Any] | None, store: ObjectStore, bucket: str, now: datetime):
    event = event or {}
    if event.get("all"):
        return discover_dates(store, bucket)
    if event.get("dates"):
        return [str(d) for d in event["dates"]]
    if event.get("dt"):
        return [str(event["dt"])]
    return [now.strftime("%Y-%m-%d")]


def _validate_dates(dates: Iterable[str]) -> list[str]:
    for d in dates:
        date.fromisoformat(d)  # raises ValueError on a malformed date
    return list(dates)


def _jsonl_gz(items: Iterable[Any]) -> bytes:
    lines = "\n".join(json.dumps(i, ensure_ascii=False, default=str) for i in items) + "\n"
    return gzip.compress(lines.encode("utf-8"))


def curate_source_day(
    store: ObjectStore,
    settings: CurateSettings,
    source: str,
    dt: str,
    now: datetime,
    to_parquet: Callable[[list[dict[str, Any]]], bytes] = parquet.to_parquet_bytes,
    emit: Callable[[str], None] = print,
) -> dict[str, Any]:
    records, bad_lines, files = read_raw_records(store, settings.raw_bucket, source, dt)
    if files == 0:
        return {"source": source, "dt": dt, "status": "no_raw_data"}

    enriched = None
    if source in ENRICHED_SOURCES:
        ids = {str(r["source_id"]) for r in records if r.get("source_id")}
        enriched = load_enriched(store, settings.raw_bucket, source, ids)
    result = curate_day(records, source, now, enriched)
    stats = {"dt": dt, "raw_files": files, **result.stats}
    if bad_lines:
        stats["rows_in"] += bad_lines
        stats["rows_rejected"] += bad_lines
        stats["rejected_by_reason"]["invalid_json"] = bad_lines

    ratio = stats["rows_rejected"] / stats["rows_in"] if stats["rows_in"] else 0.0
    stats["status"] = "too_many_rejected" if ratio > settings.max_reject_ratio else "ok"

    partition = f"dt={dt}/source={source}"
    if result.rows:
        store.write(
            settings.curated_bucket,
            f"postings/{partition}/postings.parquet",
            to_parquet(result.rows),
        )
    if result.rejected:
        store.write(
            settings.curated_bucket,
            f"quarantine/{partition}/rejected.jsonl.gz",
            _jsonl_gz(result.rejected),
        )
    store.write(
        settings.curated_bucket,
        f"quality/{partition}/report.json",
        json.dumps(stats, indent=2, default=str).encode("utf-8"),
    )
    emit(metrics.emf_line(METRICS_NAMESPACE, {"Source": source}, metrics.quality_metrics(stats)))

    return stats


def run(
    event: dict[str, Any] | None,
    store: ObjectStore,
    settings: CurateSettings,
    now: datetime | None = None,
    to_parquet: Callable[[list[dict[str, Any]]], bytes] = parquet.to_parquet_bytes,
    emit: Callable[[str], None] = print,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    dates = _validate_dates(resolve_dates(event, store, settings.raw_bucket, now))
    sources = (event or {}).get("sources", list(ALL_SOURCES))
    unknown = set(sources) - set(ALL_SOURCES)
    if unknown:
        raise ValueError(f"unknown sources requested: {sorted(unknown)}")

    summaries = [
        curate_source_day(store, settings, source, dt, now, to_parquet, emit)
        for dt in dates
        for source in sources
    ]
    failed = [s for s in summaries if s.get("status") == "too_many_rejected"]
    return {
        "days": dates,
        "summaries": summaries,
        "failed": [(s["dt"], s["source"]) for s in failed],
    }


def lambda_handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    import boto3  # provided by the Lambda runtime

    summary = run(event, S3Store(boto3.client("s3")), CurateSettings.from_env())
    log.info("curation summary: %s", json.dumps(summary, default=str))
    if summary["failed"]:
        raise RuntimeError(f"too many rejected records for: {summary['failed']}")
    return summary
