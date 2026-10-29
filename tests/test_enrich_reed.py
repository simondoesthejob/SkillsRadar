import gzip
import json
from datetime import UTC, datetime

from skillsradar.enrich import reed
from skillsradar.enrich.reed import EnrichSettings
from skillsradar.http import HttpError
from skillsradar.storage import enriched_key

NOW = datetime(2026, 10, 28, 7, 0, tzinfo=UTC)
SETTINGS = EnrichSettings(raw_bucket="raw", max_new=300, lookback_days=2, request_interval=0)


class FakeStore:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def list_keys(self, bucket, prefix):
        return sorted(k for b, k in self.objects if b == bucket and k.startswith(prefix))

    def read(self, bucket, key):
        return self.objects[(bucket, key)]

    def write(self, bucket, key, body):
        self.objects[(bucket, key)] = body


def put_raw(store, dt, ids, run="run-060000"):
    lines = "\n".join(json.dumps({"source": "reed", "source_id": i}) for i in ids) + "\n"
    key = f"raw/source=reed/dt={dt}/{run}.jsonl.gz"
    store.write("raw", key, gzip.compress(lines.encode()))


def cached(store, job_id):
    return json.loads(gzip.decompress(store.read("raw", enriched_key("reed", job_id))))


class Fetcher:
    def __init__(self, errors=None):
        self.calls: list[str] = []
        self.errors = errors or {}

    def __call__(self, job_id):
        self.calls.append(job_id)
        if job_id in self.errors:
            raise self.errors[job_id]
        return {"jobId": int(job_id), "jobDescription": f"<p>Full text {job_id}</p>"}


def test_fetches_new_ids_once_and_caches_them():
    store, fetch = FakeStore(), Fetcher()
    put_raw(store, "2026-10-27", ["1", "2"])
    put_raw(store, "2026-10-28", ["2", "3"])

    first = reed.run({}, store, SETTINGS, fetch, NOW, sleep=lambda s: None)
    assert first["candidate_ids"] == 3
    assert first["fetched"] == 3
    assert first["remaining"] == 0
    assert first["detail_keys"] == ["jobDescription", "jobId"]
    assert cached(store, "3")["jobDescription"] == "<p>Full text 3</p>"
    assert cached(store, "3")["fetched_at"] == NOW.isoformat()

    fetch.calls.clear()
    second = reed.run({}, store, SETTINGS, fetch, NOW, sleep=lambda s: None)
    assert fetch.calls == []
    assert second["already_enriched"] == 3
    assert second["fetched"] == 0


def test_newest_day_first_and_max_new_leaves_a_backlog():
    store, fetch = FakeStore(), Fetcher()
    put_raw(store, "2026-10-27", ["1"])
    put_raw(store, "2026-10-28", ["2", "3"])
    summary = reed.run({"max_new": 2}, store, SETTINGS, fetch, NOW, sleep=lambda s: None)
    assert fetch.calls == ["2", "3"]
    assert summary["remaining"] == 1


def test_lookback_limits_days_and_all_overrides_it():
    store = FakeStore()
    for n, day in enumerate(["2026-10-25", "2026-10-26", "2026-10-27", "2026-10-28"]):
        put_raw(store, day, [str(n)])
    limited = reed.run({}, store, SETTINGS, Fetcher(), NOW, sleep=lambda s: None)
    assert limited["days_scanned"] == ["2026-10-28", "2026-10-27"]
    everything = reed.run({"all": True}, store, SETTINGS, Fetcher(), NOW, sleep=lambda s: None)
    assert everything["candidate_ids"] == 4


def test_removed_posting_is_marked_gone_and_not_retried():
    store = FakeStore()
    put_raw(store, "2026-10-28", ["1"])
    fetch = Fetcher({"1": HttpError("GET failed with HTTP 404", 404)})
    summary = reed.run({}, store, SETTINGS, fetch, NOW, sleep=lambda s: None)
    assert summary["gone"] == 1
    assert cached(store, "1")["gone"] is True
    fetch.calls.clear()
    reed.run({}, store, SETTINGS, fetch, NOW, sleep=lambda s: None)
    assert fetch.calls == []


def test_rate_limit_stops_the_run_but_keeps_what_was_fetched():
    store = FakeStore()
    put_raw(store, "2026-10-28", ["1", "2", "3"])
    fetch = Fetcher({"2": HttpError("GET failed with HTTP 429", 429)})
    summary = reed.run({}, store, SETTINGS, fetch, NOW, sleep=lambda s: None)
    assert summary["stopped_reason"] == "HTTP 429"
    assert fetch.calls == ["1", "2"]
    assert summary["fetched"] == 1
    assert summary["remaining"] == 2
    assert ("raw", enriched_key("reed", "1")) in store.objects


def test_other_errors_are_counted_and_do_not_stop_a_healthy_run():
    store = FakeStore()
    put_raw(store, "2026-10-28", ["1", "2", "3"])
    fetch = Fetcher({"2": HttpError("GET failed after 4 attempts", 500)})
    summary = reed.run({}, store, SETTINGS, fetch, NOW, sleep=lambda s: None)
    assert (summary["fetched"], summary["failed"], summary["remaining"]) == (2, 1, 1)
    assert summary["stopped_reason"] is None


def test_gives_up_after_consecutive_failures():
    store = FakeStore()
    ids = [str(i) for i in range(10)]
    put_raw(store, "2026-10-28", ids)
    fetch = Fetcher({i: HttpError("boom", 500) for i in ids})
    summary = reed.run({}, store, SETTINGS, fetch, NOW, sleep=lambda s: None)
    assert summary["stopped_reason"] == "too many consecutive failures"
    assert len(fetch.calls) == 5


def test_sleeps_between_calls_only():
    store, delays = FakeStore(), []
    put_raw(store, "2026-10-28", ["1", "2", "3"])
    settings = EnrichSettings(raw_bucket="raw", request_interval=1.5)
    reed.run({}, store, settings, Fetcher(), NOW, sleep=delays.append)
    assert delays == [1.5, 1.5]
