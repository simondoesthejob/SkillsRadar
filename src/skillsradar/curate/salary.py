"""Salary normalisation to an annual figure.

Reed and Adzuna give a minimum and maximum with no pay period. Contract roles are often quoted
per day or per hour, so the period is inferred from the size of the number. This is a heuristic:
the inferred period is always recorded in `salary_basis` so analysis can filter on it.

Adzuna marks many salaries as predicted (its own estimate, not the advertiser's). Those are kept
in the raw columns but get no annual figure, so they cannot leak into salary statistics.
"""

from __future__ import annotations

HOURS_PER_YEAR = 1950  # 7.5 h x 5 days x 52 weeks
DAYS_PER_YEAR = 230  # 5 days x 52 weeks, less leave and bank holidays

HOURLY_BELOW = 150
DAILY_BELOW = 1500
ANNUAL_FROM = 10_000
IMPLAUSIBLE_ABOVE = 1_000_000


def normalise_salary(
    low: float | None, high: float | None, predicted: bool
) -> tuple[float | None, float | None, str | None]:
    """Return (annual_min, annual_max, basis).

    basis is one of: None (no salary), predicted, annual, daily_inferred, hourly_inferred,
    unrecognised (an in-between value that fits no period), implausible.
    """
    if low is None and high is None:
        return None, None, None
    if predicted:
        return None, None, "predicted"

    if low is not None and high is not None and low > high:
        low, high = high, low
    reference = high if high is not None else low
    if reference is None or reference <= 0:
        return None, None, "unrecognised"

    if reference < HOURLY_BELOW:
        factor, basis = HOURS_PER_YEAR, "hourly_inferred"
    elif reference < DAILY_BELOW:
        factor, basis = DAYS_PER_YEAR, "daily_inferred"
    elif reference < ANNUAL_FROM:
        return None, None, "unrecognised"
    else:
        factor, basis = 1, "annual"

    annual_low = round(low * factor) if low is not None else None
    annual_high = round(high * factor) if high is not None else None
    if max(v for v in (annual_low, annual_high) if v is not None) > IMPLAUSIBLE_ABOVE:
        return None, None, "implausible"
    return annual_low, annual_high, basis
