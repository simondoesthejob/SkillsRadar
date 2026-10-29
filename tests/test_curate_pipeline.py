from datetime import UTC, date, datetime

from skillsradar.curate.pipeline import curate_day
from skillsradar.curate.schema import COLUMNS

NOW = datetime(2026, 10, 20, 7, 0, tzinfo=UTC)


def raw(source="reed", source_id="1", **overrides):
    record = {
        "source": source,
        "source_id": source_id,
        "dedupe_key": f"{source}:{source_id}",
        "title": "Data Engineer",
        "company": "Acme",
        "location": "London",
        "description": "Build data pipelines in Python.",
        "url": "https://example.com/1",
        "posted_at": "2026-10-16",
        "salary_min": 50000.0,
        "salary_max": 60000.0,
        "salary_predicted": False,
        "category": None,
        "contract_type": None,
        "ingested_at": "2026-10-20T06:00:00+00:00",
    }
    return {**record, **overrides}


def test_row_has_exactly_the_schema_columns():
    result = curate_day([raw()], "reed", NOW)
    assert set(result.rows[0]) == {name for name, _ in COLUMNS}


def test_basic_row_is_normalised():
    row = curate_day([raw()], "reed", NOW).rows[0]
    assert row["posted_date"] == date(2026, 10, 16)
    assert row["salary_annual_min"] == 50000
    assert row["salary_basis"] == "annual"
    assert row["description_truncated"] is False
    assert row["observed_count"] == 1
    assert row["curated_at"] == NOW.isoformat()


def test_duplicates_within_a_day_keep_the_latest_copy():
    older = raw(description="old text", ingested_at="2026-10-20T06:00:00+00:00")
    newer = raw(description="new text", ingested_at="2026-10-20T18:00:00+00:00")
    result = curate_day([older, newer, raw(source_id="2")], "reed", NOW)
    by_key = {r["dedupe_key"]: r for r in result.rows}
    assert len(result.rows) == 2
    assert by_key["reed:1"]["description"] == "new text"
    assert by_key["reed:1"]["observed_count"] == 2
    assert by_key["reed:1"]["first_ingested_at"] == "2026-10-20T06:00:00+00:00"
    assert by_key["reed:1"]["last_ingested_at"] == "2026-10-20T18:00:00+00:00"
    assert result.stats["duplicates_removed"] == 1


def test_invalid_records_are_rejected_not_curated():
    bad = raw(source_id="2", title="")
    result = curate_day([raw(), bad], "reed", NOW)
    assert [r["source_id"] for r in result.rows] == ["1"]
    assert result.rejected[0]["reasons"] == ["missing_title"]
    assert result.stats["rows_in"] == 2
    assert result.stats["rows_rejected"] == 1
    assert result.stats["rejected_by_reason"] == {"missing_title": 1}


def test_contact_details_are_removed_and_counted():
    record = raw(description="Email me at jo@example.com or call 020 7946 0958")
    result = curate_day([record], "reed", NOW)
    assert "@" not in result.rows[0]["description"]
    assert "7946" not in result.rows[0]["description"]
    assert result.stats["emails_removed"] == 1
    assert result.stats["phones_removed"] == 1


def test_predicted_salary_gets_no_annual_figure_but_keeps_raw_values():
    row = curate_day([raw("adzuna", salary_predicted=True)], "adzuna", NOW).rows[0]
    assert row["salary_is_predicted"] is True
    assert row["salary_min"] == 50000.0
    assert row["salary_annual_min"] is None
    assert row["salary_basis"] == "predicted"


def test_truncated_descriptions_are_flagged():
    result = curate_day([raw(description="x" * 453)], "reed", NOW)
    assert result.rows[0]["description_truncated"] is True
    assert result.stats["truncated_descriptions"] == 1


def test_hacker_news_header_gives_location_and_remote():
    record = raw(
        "hn_hiring",
        title="Acme | Python Engineer | Bristol, UK | REMOTE",
        description="Acme | Python Engineer | Bristol, UK | REMOTE\nWrite to hiring@acme.io",
        location=None,
        salary_min=None,
        salary_max=None,
        posted_at="2026-10-01T09:00:00+00:00",
    )
    row = curate_day([record], "hn_hiring", NOW).rows[0]
    assert row["location"] == "Bristol, UK"
    assert row["remote"] is True
    assert row["posted_date"] == date(2026, 10, 1)
    assert "hiring@acme.io" not in row["description"]
    assert row["salary_basis"] is None


def test_unparseable_posted_date_becomes_null_and_is_counted():
    result = curate_day([raw(posted_at="not a date")], "reed", NOW)
    assert result.rows[0]["posted_date"] is None
    assert result.stats["posted_at_unparseable"] == 1


def test_empty_input():
    result = curate_day([], "reed", NOW)
    assert result.rows == []
    assert result.stats["rows_in"] == 0


def test_cached_full_description_replaces_truncated_search_text():
    short = "x" * 460  # looks truncated for Reed
    detail = {
        "jobId": 1,
        "jobDescription": "<p>The <b>full</b> description</p><ul><li>Python</li></ul>",
    }
    result = curate_day([raw(description=short)], "reed", NOW, {"1": detail})
    row = result.rows[0]
    assert row["description"] == "The full description\n\n- Python"
    assert row["description_truncated"] is False
    assert result.stats["descriptions_enriched"] == 1
    assert "truncated_descriptions" not in result.stats


def test_without_a_cached_detail_the_search_text_is_kept_and_flagged():
    result = curate_day(
        [raw(description="y" * 460)], "reed", NOW, {"other": {"jobDescription": "z"}}
    )
    assert result.rows[0]["description_truncated"] is True
    assert "descriptions_enriched" not in result.stats


def test_gone_marker_and_empty_detail_are_ignored():
    for detail in ({"jobId": 1, "gone": True}, {"jobId": 1, "jobDescription": ""}):
        result = curate_day([raw(description="y" * 460)], "reed", NOW, {"1": detail})
        assert result.rows[0]["description"] == "y" * 460
        assert result.rows[0]["description_truncated"] is True


def test_enriched_description_still_has_contact_details_removed():
    detail = {"jobDescription": "<p>Email jobs@agency.example or call 020 7946 0958</p>"}
    result = curate_day([raw()], "reed", NOW, {"1": detail})
    assert "jobs@agency.example" not in result.rows[0]["description"]
    assert result.stats["emails_removed"] == 1
    assert result.stats["phones_removed"] == 1
