from skillsradar.gold.sample import build_sample, latest_per_posting, stratified_sample, title_group

LONG = "x" * 300


def row(n, source="reed", title="Data Scientist", dt="2026-10-30", description=LONG, **extra):
    return {
        "dedupe_key": f"{source}:{n}",
        "source": source,
        "dt": dt,
        "title": title,
        "description": description,
        "company": "Acme",
        "location": "London",
        "url": "https://example.com",
        "salary_min": 1.0,
        **extra,
    }


def test_title_groups():
    assert title_group("Senior Data Scientist") == "ml_science"
    assert title_group("Machine Learning Engineer") == "ml_science"
    assert title_group("Data Engineer") == "data_engineering"
    assert title_group("Business Intelligence Developer") == "analytics"
    assert title_group("DevOps Engineer") == "devops_cloud"
    assert title_group("Backend Developer") == "software"
    assert title_group("Office Manager") == "other"
    assert title_group(None) == "other"


def test_latest_snapshot_per_posting_wins():
    rows = [row(1, dt="2026-10-28"), row(1, dt="2026-10-30"), row(2, dt="2026-10-29")]
    kept = {r["dedupe_key"]: r["dt"] for r in latest_per_posting(rows)}
    assert kept == {"reed:1": "2026-10-30", "reed:2": "2026-10-29"}


def test_sample_is_repeatable_and_covers_every_group():
    titles = [
        "Data Scientist",
        "Data Engineer",
        "Data Analyst",
        "DevOps Engineer",
        "Software Engineer",
    ]
    rows = [row(i, title=titles[i % 5]) for i in range(100)]
    first = stratified_sample(rows, 10, seed=7)
    assert [r["dedupe_key"] for r in first] == [
        r["dedupe_key"] for r in stratified_sample(rows, 10, seed=7)
    ]
    assert {title_group(r["title"]) for r in first} == {
        "ml_science", "data_engineering", "analytics", "devops_cloud", "software",
    }  # fmt: skip
    different = stratified_sample(rows, 10, seed=8)
    assert [r["dedupe_key"] for r in different] != [r["dedupe_key"] for r in first]


def test_quotas_per_source_and_short_text_is_dropped():
    rows = (
        [row(i) for i in range(10)]
        + [row(i, source="hn_hiring") for i in range(10)]
        + [row(99, description="too short")]
    )
    items = build_sample(rows, {"reed": 4, "hn_hiring": 3})
    assert sorted(i["source"] for i in items) == ["hn_hiring"] * 3 + ["reed"] * 4
    assert "reed:99" not in {i["id"] for i in items}


def test_extending_never_repeats_or_reshuffles():
    rows = [row(i) for i in range(30)]
    first = build_sample(rows, {"reed": 5})
    more = build_sample(rows, {"reed": 5}, exclude_ids=[i["id"] for i in first])
    assert not {i["id"] for i in first} & {i["id"] for i in more}
    assert len(more) == 5


def test_items_carry_text_but_no_salary():
    item = build_sample([row(1)], {"reed": 1})[0]
    assert set(item) == {"id", "source", "dt", "title", "company", "location", "url", "description"}
