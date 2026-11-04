from datetime import UTC, datetime

import pytest

from skillsradar.gold.store import LabelStore, read_jsonl, write_jsonl

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def test_labels_are_saved_and_reloaded(tmp_path):
    path = tmp_path / "labels.jsonl"
    store = LabelStore(path)
    saved = store.upsert("reed:1", ["Python", "SQL"], notes=" note ", now=NOW)
    assert saved["skills"] == ["Python", "SQL"]
    assert saved["notes"] == "note"
    assert saved["revisions"] == 0
    assert LabelStore(path).all()["reed:1"]["skills"] == ["Python", "SQL"]


def test_relabelling_replaces_and_counts_revisions(tmp_path):
    store = LabelStore(tmp_path / "labels.jsonl")
    store.upsert("reed:1", ["Python"], now=NOW)
    again = store.upsert("reed:1", ["Python", "dbt"], now=NOW)
    assert again["revisions"] == 1
    assert len(read_jsonl(tmp_path / "labels.jsonl")) == 1


def test_skills_are_tidied_and_deduplicated_case_insensitively(tmp_path):
    store = LabelStore(tmp_path / "labels.jsonl")
    saved = store.upsert("a", ["  Python ", "python", "", "Power   BI"], now=NOW)
    assert saved["skills"] == ["Python", "Power BI"]


def test_a_skipped_posting_keeps_no_skills(tmp_path):
    saved = LabelStore(tmp_path / "labels.jsonl").upsert("a", ["Python"], status="skip", now=NOW)
    assert saved["skills"] == [] and saved["status"] == "skip"


def test_unknown_status_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        LabelStore(tmp_path / "labels.jsonl").upsert("a", [], status="maybe")


def test_write_leaves_no_temp_files_and_creates_folders(tmp_path):
    path = tmp_path / "nested" / "out.jsonl"
    write_jsonl(path, [{"id": 1}, {"id": 2}])
    assert read_jsonl(path) == [{"id": 1}, {"id": 2}]
    assert [p.name for p in path.parent.iterdir()] == ["out.jsonl"]
    assert read_jsonl(tmp_path / "missing.jsonl") == []


def test_review_fields_are_kept_until_changed(tmp_path):
    store = LabelStore(tmp_path / "labels.jsonl")
    store.upsert("a", ["Python", "dbt"])
    first = store.upsert(
        "a", ["Python", "dbt"], rejected=["Java"], review_added=["dbt"], reviewed=True
    )
    assert first["rejected"] == ["Java"] and first["reviewed"] is True
    again = store.upsert("a", ["Python", "dbt"], notes="n")  # fields left out are kept
    assert again["rejected"] == ["Java"] and again["review_added"] == ["dbt"]
    cleared = store.upsert(
        "a", ["Python"], rejected=[]
    )  # explicit empty clears; removed skill goes
    assert "rejected" not in cleared and "review_added" not in cleared
    assert LabelStore(tmp_path / "labels.jsonl").all()["a"]["reviewed"] is True
