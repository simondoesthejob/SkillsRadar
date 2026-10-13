from skillsradar.sources.adzuna import AdzunaSource


def make_result(job_id: int) -> dict:
    return {
        "id": str(job_id),
        "title": " Data Scientist ",
        "company": {"display_name": "Acme Ltd"},
        "location": {"display_name": "Reading, Berkshire"},
        "description": "Python, SQL and some machine learning.",
        "redirect_url": f"https://www.adzuna.co.uk/jobs/details/{job_id}",
        "created": "2026-10-01T09:00:00Z",
        "salary_min": 50000.0,
        "salary_max": 65000.0,
        "salary_is_predicted": "1",
        "category": {"label": "IT Jobs"},
        "contract_type": "permanent",
    }


def test_parse_maps_fields():
    posting = AdzunaSource.parse(make_result(1))
    assert posting.dedupe_key == "adzuna:1"
    assert posting.title == "Data Scientist"
    assert posting.company == "Acme Ltd"
    assert posting.location == "Reading, Berkshire"
    assert posting.salary_predicted is True
    assert posting.category == "IT Jobs"


def test_parse_tolerates_missing_optional_fields():
    posting = AdzunaSource.parse({"id": 7, "title": "Engineer"})
    assert posting.company is None
    assert posting.salary_min is None
    assert posting.salary_predicted is False


def test_fetch_pages_and_respects_interval():
    calls, sleeps = [], []

    def fake_fetch(url, params):
        calls.append((url, params["what"]))
        return {"results": [make_result(len(calls)), make_result(len(calls) + 100)]}

    source = AdzunaSource(
        "id",
        "key",
        queries=("python", "mlops"),
        pages_per_query=2,
        results_per_page=2,
        request_interval=2.5,
        fetch_json=fake_fetch,
        sleep=sleeps.append,
    )
    postings = list(source.fetch())

    assert len(calls) == 4  # 2 queries x 2 pages
    assert len(postings) == 8
    assert sleeps == [2.5, 2.5, 2.5]  # no sleep before the first call
    assert calls[0][0].endswith("/gb/search/1")
    assert calls[1][0].endswith("/gb/search/2")


def test_fetch_stops_at_short_page():
    def fake_fetch(url, params):
        return {"results": [make_result(1)]}  # fewer than results_per_page

    source = AdzunaSource(
        "id",
        "key",
        queries=("python",),
        pages_per_query=5,
        results_per_page=50,
        fetch_json=fake_fetch,
        sleep=lambda _: None,
    )
    assert len(list(source.fetch())) == 1
    assert source.requests_made == 1
