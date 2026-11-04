import pytest

from skillsradar.http import HttpError
from skillsradar.sources.devitjobs import (
    DevITjobsSource,
    parse_pubdate,
    parse_salary,
    refuse_unsafe_xml,
    stable_id,
)


def job_xml(job_id="60759a28a4a6990017d94bf3-W44", **fields):
    values = {
        "title": "Web portal Developer",
        "link": "https://devitjobs.uk/jobs/EllisKnight-Web-portal-Developer",
        "city": "London",
        "location": "Colchester,, London",
        "salary": "£35,000 - 40,000 per year",
        "company": "EllisKnight",
        "jobtype": "Full-Time",
        "pubdate": "04.10.2023",
        "description": "<p>Python &amp; SQL</p><ul><li>•</li><li>React</li></ul>",
        **fields,
    }
    body = "".join(f"<{k}><![CDATA[{v}]]></{k}>" for k, v in values.items() if v is not None)
    return f'<job id="{job_id}" category="IT"><id><![CDATA[{job_id}]]></id>{body}</job>'


def feed(*jobs):
    return ('<?xml version="1.0" encoding="UTF-8"?><jobs>' + "".join(jobs) + "</jobs>").encode()


def fetch(data):
    source = DevITjobsSource(fetch_bytes=lambda url, **kw: data)
    return list(source.fetch())


def test_the_weekly_tag_is_removed_from_the_id():
    assert stable_id("60759a28a4a6990017d94bf3-W44") == "60759a28a4a6990017d94bf3"
    assert stable_id("60759a28a4a6990017d94bf3-W45") == stable_id("60759a28a4a6990017d94bf3-W44")
    assert stable_id("abc") == "abc"


def test_salary_parsing():
    assert parse_salary("£35,000 - 40,000 per year") == (35000.0, 40000.0)
    assert parse_salary("£40,000 - 40,000 per year") == (40000.0, 40000.0)
    assert parse_salary("£45,000 per year") == (45000.0, 45000.0)
    assert parse_salary("£? - ? per year") == (None, None)
    assert parse_salary("") == (None, None) and parse_salary(None) == (None, None)


def test_pubdate_is_day_first_with_dots():
    assert parse_pubdate("04.10.2023") == "2023-10-04"
    assert parse_pubdate("30.10.2026") == "2026-10-30"
    assert parse_pubdate("soon") == "soon"
    assert parse_pubdate(" ") is None and parse_pubdate(None) is None


def test_posting_fields_are_mapped():
    (posting,) = fetch(feed(job_xml()))
    assert posting.dedupe_key == "devitjobs:60759a28a4a6990017d94bf3"
    assert posting.title == "Web portal Developer" and posting.company == "EllisKnight"
    assert posting.location == "London"  # the clean city, not the street-level location
    assert posting.url == "https://devitjobs.uk/jobs/EllisKnight-Web-portal-Developer"
    assert posting.posted_at == "2023-10-04"
    assert (posting.salary_min, posting.salary_max) == (35000.0, 40000.0)
    assert posting.contract_type == "Full-Time"
    assert "<li>React</li>" in posting.description  # HTML kept; converted when curated


def test_missing_salary_and_city_fall_back_gracefully():
    (posting,) = fetch(feed(job_xml(salary="£? - ? per year", city="")))
    assert posting.salary_min is None and posting.salary_max is None
    assert posting.location == "London"  # last part of "Colchester,, London"


def test_entries_without_id_or_title_and_duplicate_ids_are_skipped():
    data = feed(
        job_xml(),
        job_xml(job_id="60759a28a4a6990017d94bf3-W45"),  # same posting, different week tag
        job_xml(job_id="bbb-W44", title=""),
        job_xml(job_id="ccc-W44", title="Other"),
    )
    assert [p.source_id for p in fetch(data)] == ["60759a28a4a6990017d94bf3", "ccc"]


def test_unsafe_or_malformed_feeds_are_refused():
    with pytest.raises(ValueError, match="DOCTYPE"):
        refuse_unsafe_xml(b'<?xml version="1.0"?><!DOCTYPE jobs [<!ENTITY a "b">]><jobs/>')
    with pytest.raises(ValueError, match="DOCTYPE"):
        fetch(b'<?xml version="1.0"?><!doctype jobs><jobs/>')
    with pytest.raises(HttpError, match="not valid XML"):
        fetch(b"<jobs><job>")
    with pytest.raises(HttpError, match="unexpected feed root"):
        fetch(b"<html></html>")


def test_fetch_asks_for_a_size_limit_and_a_long_timeout():
    seen = {}

    def fake(url, **kwargs):
        seen.update(url=url, **kwargs)
        return feed()

    assert list(DevITjobsSource(fetch_bytes=fake).fetch()) == []
    assert seen["url"].endswith("/job_feed.xml") and seen["max_bytes"] and seen["timeout"] >= 30
