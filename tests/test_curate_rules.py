from datetime import date

import pytest

from skillsradar.curate.rules import hard_failures, is_truncated, parse_posted_date


def good(**overrides):
    record = {
        "source": "reed",
        "source_id": "1",
        "title": "Data Engineer",
        "description": "Build pipelines",
        "salary_min": None,
        "salary_max": None,
    }
    return {**record, **overrides}


def test_valid_record_has_no_failures():
    assert hard_failures(good(), "reed") == []


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"source_id": ""}, "missing_source_id"),
        ({"source_id": None}, "missing_source_id"),
        ({"title": "   "}, "missing_title"),
        ({"description": ""}, "missing_description"),
        ({"source": "adzuna"}, "source_mismatch"),
        ({"salary_min": -5}, "invalid_salary_min"),
        ({"salary_max": "lots"}, "invalid_salary_max"),
    ],
)
def test_failures(overrides, reason):
    assert reason in hard_failures(good(**overrides), "reed")


@pytest.mark.parametrize(
    ("source", "text", "expected"),
    [
        ("reed", "x" * 453, True),
        ("reed", "x" * 449, False),
        ("adzuna", "x" * 500, True),
        ("adzuna", "x" * 499, False),
        ("adzuna", "short text...", True),
        ("reed", "short text…", True),
        ("adzuna", "short complete text", False),
        ("hn_hiring", "x" * 5000, False),
        ("hn_hiring", "ends with...", False),
    ],
)
def test_is_truncated(source, text, expected):
    assert is_truncated(source, text) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-16", date(2026, 10, 16)),
        ("2026-10-16T09:30:00+00:00", date(2026, 10, 16)),
        (None, None),
        ("", None),
        ("16/10/2026", None),
        ("2026-13-45", None),
    ],
)
def test_parse_posted_date(value, expected):
    assert parse_posted_date(value) == expected
