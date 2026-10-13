import base64

from skillsradar.sources.reed import ReedSource, basic_auth_header, normalise_date


def make_result(job_id: int) -> dict:
    return {
        "jobId": job_id,
        "employerName": "Acme Ltd",
        "jobTitle": " Machine Learning Engineer ",
        "locationName": "Slough",
        "minimumSalary": 60000.0,
        "maximumSalary": 80000.0,
        "date": "03/10/2026",
        "jobDescription": "Python, AWS and SageMaker...",
        "jobUrl": f"https://www.reed.co.uk/jobs/ml-engineer/{job_id}",
    }


def test_basic_auth_uses_key_as_username_with_empty_password():
    header = basic_auth_header("secret-key")["Authorization"]
    assert header.startswith("Basic ")
    assert base64.b64decode(header.removeprefix("Basic ")).decode() == "secret-key:"


def test_normalise_date_is_day_first_and_tolerant():
    assert normalise_date("03/10/2026") == "2026-10-03"
    assert normalise_date("2026-10-03") == "2026-10-03"
    assert normalise_date("not a date") == "not a date"
    assert normalise_date(None) is None


def test_parse_maps_fields():
    posting = ReedSource.parse(make_result(7))
    assert posting.dedupe_key == "reed:7"
    assert posting.title == "Machine Learning Engineer"
    assert posting.company == "Acme Ltd"
    assert posting.posted_at == "2026-10-03"
    assert posting.salary_min == 60000.0
    assert posting.url.endswith("/7")


def test_parse_tolerates_missing_optional_fields():
    posting = ReedSource.parse({"jobId": 9})
    assert posting.title == ""
    assert posting.company is None
    assert posting.salary_max is None


def test_fetch_pages_with_skip_sends_auth_and_respects_interval():
    calls, sleeps = [], []

    def fake_fetch(url, params, headers=None):
        calls.append((params, headers))
        return {"results": [make_result(len(calls)), make_result(len(calls) + 100)]}

    source = ReedSource(
        "key",
        queries=("python", "mlops"),
        location="London",
        pages_per_query=2,
        results_per_page=2,
        request_interval=1.0,
        fetch_json=fake_fetch,
        sleep=sleeps.append,
    )
    postings = list(source.fetch())

    assert len(calls) == 4 and len(postings) == 8
    assert sleeps == [1.0, 1.0, 1.0]
    assert [c[0]["resultsToSkip"] for c in calls] == [0, 2, 0, 2]
    assert calls[0][0]["locationName"] == "London"
    assert calls[0][1]["Authorization"].startswith("Basic ")


def test_fetch_stops_at_short_page_and_caps_page_size():
    def fake_fetch(url, params, headers=None):
        assert params["resultsToTake"] == 100  # documented maximum
        assert "locationName" not in params  # UK-wide by default
        return {"results": [make_result(1)]}

    source = ReedSource(
        "key",
        queries=("python",),
        pages_per_query=5,
        results_per_page=500,
        fetch_json=fake_fetch,
        sleep=lambda _: None,
    )
    assert len(list(source.fetch())) == 1
    assert source.requests_made == 1
