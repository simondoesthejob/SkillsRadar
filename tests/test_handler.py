import gzip
import json
from datetime import UTC, datetime

import pytest

from skillsradar import handler
from skillsradar.config import Settings
from skillsradar.http import HttpError, get_json
from skillsradar.models import JobPosting

NOW = datetime(2026, 10, 4, 12, 30, 15, tzinfo=UTC)


def posting(job_id: str) -> JobPosting:
    return JobPosting(
        source="fake",
        source_id=job_id,
        title="t",
        company="c",
        location=None,
        description="d",
        url=None,
        posted_at=None,
    )


class FakeSource:
    def __init__(self, name, postings=(), error=None):
        self.name, self._postings, self._error = name, postings, error

    def fetch(self):
        if self._error:
            raise self._error
        yield from self._postings


def test_object_key_is_hive_partitioned():
    key = handler.object_key("adzuna", NOW)
    assert key == "raw/source=adzuna/dt=2026-10-04/run-123015.jsonl.gz"


def test_run_writes_gzipped_jsonl_with_ingest_metadata():
    written = {}
    summary = handler.run(
        [FakeSource("fake", [posting("1"), posting("2")])],
        "bucket",
        lambda bucket, key, body: written.update({(bucket, key): body}),
        now=NOW,
    )
    assert summary == {"written": {"fake": 2}, "errors": {}}
    (((bucket, key), body),) = written.items()
    assert bucket == "bucket" and key.startswith("raw/source=fake/dt=2026-10-04/")
    rows = [json.loads(line) for line in gzip.decompress(body).decode().splitlines()]
    assert [r["dedupe_key"] for r in rows] == ["fake:1", "fake:2"]
    assert rows[0]["ingested_at"] == NOW.isoformat()


def test_one_failing_source_does_not_lose_the_others():
    written = []
    summary = handler.run(
        [FakeSource("bad", error=ValueError("boom")), FakeSource("ok", [posting("1")])],
        "bucket",
        lambda *args: written.append(args),
        now=NOW,
    )
    assert summary["errors"] == {"bad": "boom"}
    assert summary["written"] == {"ok": 1}
    assert len(written) == 1


def test_empty_source_writes_nothing():
    written = []
    handler.run([FakeSource("empty")], "bucket", lambda *a: written.append(a), now=NOW)
    assert written == []


def test_settings_from_env_parses_queries():
    settings = Settings.from_env({"RAW_BUCKET": "b", "ADZUNA_QUERIES": "a, b ,,c"})
    assert settings.adzuna_queries == ("a", "b", "c")
    assert settings.raw_bucket == "b"


def test_get_json_retries_transient_errors_then_raises():
    import urllib.error

    attempts, sleeps = [], []

    def failing_opener(request, timeout):
        attempts.append(1)
        raise urllib.error.HTTPError(request.full_url, 503, "unavailable", {}, None)

    with pytest.raises(HttpError):
        get_json("https://example.test", retries=2, opener=failing_opener, sleep=sleeps.append)
    assert len(attempts) == 3
    assert sleeps == [1.5, 3.0]


def test_http_error_carries_the_status_code():
    import urllib.error

    def opener(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    with pytest.raises(HttpError) as excinfo:
        get_json("https://example.com/x", opener=opener, sleep=lambda s: None)
    assert excinfo.value.status == 404
