import pytest

from skillsradar.curate.salary import normalise_salary


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
