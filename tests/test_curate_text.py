import pytest

from skillsradar.curate.text import strip_pii


@pytest.mark.parametrize(
    "raw",
    [
        "Apply to jobs@example.co.uk today",
        "Email first.last+hiring@sub.example.com for details",
    ],
)
def test_emails_are_removed(raw):
    cleaned, counts = strip_pii(raw)
    assert "@" not in cleaned
    assert "[email removed]" in cleaned
    assert counts == {"emails": 1, "phones": 0}


@pytest.mark.parametrize(
    "raw",
    [
        "Call +44 20 7946 0958 now",
        "Call 020 7946 0958 now",
        "Call 07700 900123 now",
        "Call 02079460958 now",
        "Call (415) 555-0132 now",
        "Call 415-555-0132 now",
        "Call +1 415 555 0132 now",
    ],
)
def test_phone_numbers_are_removed(raw):
    cleaned, counts = strip_pii(raw)
    assert "[phone removed]" in cleaned
    assert counts["phones"] == 1
    assert not any(ch.isdigit() for ch in cleaned.replace("[phone removed]", ""))


@pytest.mark.parametrize(
    "raw",
    [
        "Salary £45,000 - £55,000 plus bonus",
        "Salary 45000-55000 per annum",
        "Salary 100000 - 120000",
        "Experience 2019-2024 in Python",
        "Day rate £450-£550",
        "Up to 120k, 4.5 years of experience",
    ],
)
def test_salaries_and_dates_are_left_alone(raw):
    cleaned, counts = strip_pii(raw)
    assert cleaned == raw
    assert counts == {"emails": 0, "phones": 0}


def test_handles_none_and_empty():
    assert strip_pii(None) == (None, {"emails": 0, "phones": 0})
    assert strip_pii("") == ("", {"emails": 0, "phones": 0})
