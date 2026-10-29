import pytest

from skillsradar.curate.salary import normalise_salary, parse_period


def test_no_salary():
    assert normalise_salary(None, None, False) == (None, None, None)


def test_predicted_salaries_get_no_annual_figure():
    assert normalise_salary(50000, 60000, True) == (None, None, "predicted")


def test_annual_salary_is_kept():
    assert normalise_salary(45000, 55000, False) == (45000, 55000, "annual")


def test_hourly_rate_is_annualised():
    assert normalise_salary(40, 60, False) == (40 * 1950, 60 * 1950, "hourly_inferred")


def test_daily_rate_is_annualised():
    assert normalise_salary(400, 550, False) == (400 * 230, 550 * 230, "daily_inferred")


def test_single_value_uses_whichever_is_present():
    assert normalise_salary(None, 60000, False) == (None, 60000, "annual")
    assert normalise_salary(60000, None, False) == (60000, None, "annual")


def test_reversed_range_is_swapped():
    assert normalise_salary(55000, 45000, False) == (45000, 55000, "annual")


@pytest.mark.parametrize("value", [1500, 3000, 9999])
def test_in_between_values_are_unrecognised(value):
    assert normalise_salary(value, value, False) == (None, None, "unrecognised")


def test_zero_is_unrecognised():
    assert normalise_salary(0, 0, False) == (None, None, "unrecognised")


def test_absurd_values_are_flagged():
    assert normalise_salary(5_000_000, 6_000_000, False) == (None, None, "implausible")


@pytest.mark.parametrize(
    ("text", "period"),
    [
        ("per annum", "annual"),
        ("Per Annum", "annual"),
        ("annual", "annual"),
        ("per year", "annual"),
        ("per month", "monthly"),
        ("per week", "weekly"),
        ("per day", "daily"),
        ("Daily", "daily"),
        ("per hour", "hourly"),
        ("hourly", "hourly"),
        ("", None),
        (None, None),
        ("negotiable", None),
        ("competitive", None),
    ],
)
def test_parse_period(text, period):
    assert parse_period(text) == period


def test_reported_period_is_used_even_where_size_would_say_otherwise():
    # 800 a day would be inferred as daily anyway; 1200 a week is "unrecognised" by size alone
    assert normalise_salary(1000, 1200, False, "weekly") == (52000, 62400, "weekly_reported")
    assert normalise_salary(45000, 55000, False, "annual") == (45000, 55000, "annual_reported")
    assert normalise_salary(400, 550, False, "daily") == (400 * 230, 550 * 230, "daily_reported")
    assert normalise_salary(40, 60, False, "hourly") == (40 * 1950, 60 * 1950, "hourly_reported")
    assert normalise_salary(4000, 5000, False, "monthly") == (48000, 60000, "monthly_reported")


def test_a_reported_period_that_gives_an_implausible_year_is_distrusted():
    assert normalise_salary(45, 55, False, "annual")[2] == "hourly_inferred"
    assert normalise_salary(45000, 55000, False, "daily")[2] == "annual"


def test_predicted_and_missing_salaries_ignore_the_period():
    assert normalise_salary(50000, 60000, True, "annual") == (None, None, "predicted")
    assert normalise_salary(None, None, False, "annual") == (None, None, None)
