import gzip
import json
from datetime import UTC, datetime

import pytest

from skillsradar.curate import handler
from skillsradar.curate.handler import CurateSettings

NOW = datetime(2026, 10, 20, 7, 0, tzinfo=UTC)
SETTINGS = CurateSettings(raw_bucket="raw", curated_bucket="curated")


class FakeStore:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def list_keys(self, bucket, prefix):
        return sorted(k for b, k in self.objects if b == bucket and k.startswith(prefix))

    def read(self, bucket, key):
        return self.objects[(bucket, key)]

    def write(self, bucket, key, body):
        self.objects[(bucket, key)] = body


def record(source="reed", source_id="1", **overrides):
    base = {
        "source": source,
        "source_id": source_id,
        "dedupe_key": f"{source}:{source_id}",
        "title": "Data Engineer",
        "company": "Acme",
        "location": "London",
        "description": "Build pipelines",
        "url": None,
        "posted_at": "2026-10-16",
        "salary_min": None,
        "salary_max": None,
        "salary_predicted": False,
        "ingested_at": "2026-10-20T06:00:00+00:00",
    }
    return {**base, **overrides}


def put_raw(store, source, dt, lines, run="run-060000"):
    body = "\n".join(x if isinstance(x, str) else json.dumps(x) for x in lines) + "\n"
    store.write("raw", f"raw/source={source}/dt={dt}/{run}.jsonl.gz", gzip.compress(body.encode()))


def fake_parquet(rows):
    return json.dumps(rows, default=str).encode()


def run(store, event=None, emitted=None):
    return handler.run(
        event,
        store,
        SETTINGS,
        now=NOW,
        to_parquet=fake_parquet,
        emit=(emitted.append if emitted is not None else lambda _line: None),
    )


def test_curates_a_day_and_writes_outputs():
    store = FakeStore()
    put_raw(store, "reed", "2026-10-20", [record(), record(source_id="2")])
    summary = run(store, {"dt": "2026-10-20", "sources": ["reed"]})

    assert summary["failed"] == []
    keys = store.list_keys("curated", "")
    assert keys == [
        "postings/dt=2026-10-20/source=reed/postings.parquet",
        "quality/dt=2026-10-20/source=reed/report.json",
    ]
    report = json.loads(store.read("curated", keys[1]))
    assert report["rows_in"] == 2 and report["rows_out"] == 2 and report["status"] == "ok"


def test_rerun_is_idempotent():
    store = FakeStore()
    put_raw(store, "reed", "2026-10-20", [record()])
    run(store, {"dt": "2026-10-20", "sources": ["reed"]})
    first = dict(store.objects)
    run(store, {"dt": "2026-10-20", "sources": ["reed"]})
    assert set(store.objects) == set(first)


def test_multiple_ingestion_runs_in_a_day_are_combined_and_deduplicated():
    store = FakeStore()
    put_raw(store, "reed", "2026-10-20", [record()], run="run-060000")
    put_raw(store, "reed", "2026-10-20", [record(), record(source_id="2")], run="run-120000")
    summary = run(store, {"dt": "2026-10-20", "sources": ["reed"]})
    stats = summary["summaries"][0]
    assert stats["raw_files"] == 2
    assert stats["rows_in"] == 3 and stats["rows_out"] == 2 and stats["duplicates_removed"] == 1


def test_source_with_no_raw_data_is_skipped():
    store = FakeStore()
    put_raw(store, "reed", "2026-10-20", [record()])
    summary = run(store, {"dt": "2026-10-20"})
    statuses = {s["source"]: s["status"] for s in summary["summaries"]}
    assert statuses == {"adzuna": "no_raw_data", "reed": "ok", "hn_hiring": "no_raw_data"}


def test_rejected_records_are_quarantined_and_too_many_fails_the_run():
    store = FakeStore()
    put_raw(store, "reed", "2026-10-20", [record(), record(source_id="2", title="")])
    summary = run(store, {"dt": "2026-10-20", "sources": ["reed"]})
    assert summary["failed"] == [("2026-10-20", "reed")]
    quarantine = store.read("curated", "quarantine/dt=2026-10-20/source=reed/rejected.jsonl.gz")
    rejected = json.loads(gzip.decompress(quarantine).decode().splitlines()[0])
    assert rejected["reasons"] == ["missing_title"]
    assert ("curated", "postings/dt=2026-10-20/source=reed/postings.parquet") in store.objects


def test_malformed_json_lines_count_as_rejections():
    store = FakeStore()
    put_raw(store, "reed", "2026-10-20", [record(), "{not json", "[1, 2]"])
    stats = run(store, {"dt": "2026-10-20", "sources": ["reed"]})["summaries"][0]
    assert stats["rows_rejected"] == 2
    assert stats["rejected_by_reason"]["invalid_json"] == 2


def test_dates_all_discovers_days_in_the_raw_bucket():
    store = FakeStore()
    put_raw(store, "reed", "2026-10-18", [record()])
    put_raw(store, "adzuna", "2026-10-19", [record("adzuna")])
    summary = run(store, {"all": True})
    assert summary["days"] == ["2026-10-18", "2026-10-19"]


def test_default_is_today_in_utc():
    store = FakeStore()
    assert run(store)["days"] == ["2026-10-20"]


def test_dates_list_and_validation():
    store = FakeStore()
    assert run(store, {"dates": ["2026-10-18", "2026-10-19"], "sources": ["reed"]})["days"] == [
        "2026-10-18",
        "2026-10-19",
    ]
    with pytest.raises(ValueError):
        run(store, {"dt": "20-10-2026"})


def test_unknown_source_is_an_error():
    with pytest.raises(ValueError, match="unknown sources"):
        run(FakeStore(), {"sources": ["linkedin"]})


def test_emits_one_metrics_line_per_source_day():
    store = FakeStore()
    put_raw(store, "reed", "2026-10-20", [record()])
    emitted: list[str] = []
    run(store, {"dt": "2026-10-20", "sources": ["reed"]}, emitted)
    line = json.loads(emitted[0])
    assert line["Source"] == "reed" and line["RowsIn"] == 1
    assert line["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "SkillsRadar/Curation"


def test_settings_from_env():
    s = CurateSettings.from_env(
        {"RAW_BUCKET": "r", "CURATED_BUCKET": "c", "MAX_REJECT_RATIO": "0.1"}
    )
    assert (s.raw_bucket, s.curated_bucket, s.max_reject_ratio) == ("r", "c", 0.1)


def test_reed_day_uses_cached_full_descriptions():
    from skillsradar.storage import enriched_key

    store = FakeStore()
    put_raw(
        store,
        "reed",
        "2026-10-20",
        [record("reed", "1", description="x" * 460), record("reed", "2")],
    )
    detail = {"jobId": 1, "jobDescription": "<p>Full text</p>"}
    store.write("raw", enriched_key("reed", "1"), gzip.compress(json.dumps(detail).encode()))

    stats = handler.curate_source_day(
        store, SETTINGS, "reed", "2026-10-20", NOW, to_parquet=fake_parquet, emit=lambda s: None
    )
    assert stats["descriptions_enriched"] == 1
    rows = json.loads(store.read("curated", "postings/dt=2026-10-20/source=reed/postings.parquet"))
    by_id = {r["source_id"]: r for r in rows}
    assert by_id["1"]["description"] == "Full text"
    assert by_id["1"]["description_truncated"] is False
    assert by_id["2"]["description"] == "Build pipelines"


def test_other_sources_do_not_look_for_cached_details():
    store = FakeStore()
    put_raw(store, "adzuna", "2026-10-20", [record("adzuna", "1")])
    stats = handler.curate_source_day(
        store, SETTINGS, "adzuna", "2026-10-20", NOW, to_parquet=fake_parquet, emit=lambda s: None
    )
    assert "descriptions_enriched" not in stats
