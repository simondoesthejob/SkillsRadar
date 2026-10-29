"""Salary normalisation to an annual figure.

Adzuna and Reed search results give a minimum and maximum with no pay period. Contract roles are
often quoted per day or per hour, so by default the period is inferred from the size of the
number. This is a heuristic. Reed's per-job detail does state the period (`salaryType`); when it
is available it is used instead and recorded as `<period>_reported`. Either way `salary_basis`
says how the annual figure was reached, so analysis can filter on it.

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
REPORTED_ANNUAL_FLOOR = 5_000  # a reported period that gives less than this a year is distrusted

# Multipliers to a year for a pay period stated by the source.
PERIOD_FACTORS = {
    "annual": 1,
    "monthly": 12,
    "weekly": 52,
    "daily": DAYS_PER_YEAR,
    "hourly": HOURS_PER_YEAR,
}
_PERIOD_WORDS = (
    ("annual", ("annum", "annual", "year", "yr", "pa")),
    ("monthly", ("month",)),
    ("weekly", ("week",)),
    ("daily", ("day", "daily")),
    ("hourly", ("hour", "hr")),
)


def parse_period(salary_type: str | None) -> str | None:
    """Map a source's pay-period text ("per annum", "per day", ...) to a period name, or None."""
    if not salary_type:
        return None
    words = {w for w in "".join(c if c.isalpha() else " " for c in salary_type.lower()).split()}
    for period, keys in _PERIOD_WORDS:
        if any(k in words or (len(k) > 3 and any(w.startswith(k) for w in words)) for k in keys):
            return period
    return None


def normalise_salary(
    low: float | None, high: float | None, predicted: bool, period: str | None = None
) -> tuple[float | None, float | None, str | None]:
    """Return (annual_min, annual_max, basis).

    `period` is the pay period when the source states it (see `parse_period`). If it gives an
    implausible annual figure (a stated "per annum" on a value of 45, say) it is distrusted and the
    period is inferred from the size of the number instead.

    basis is one of: None (no salary), predicted, <period>_reported, annual, daily_inferred,
    hourly_inferred, unrecognised (an in-between value that fits no period), implausible.
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

    if period in PERIOD_FACTORS:
        factor = PERIOD_FACTORS[period]
        annual_low = round(low * factor) if low is not None else None
        annual_high = round(high * factor) if high is not None else None
        top = max(v for v in (annual_low, annual_high) if v is not None)
        if REPORTED_ANNUAL_FLOOR <= top <= IMPLAUSIBLE_ABOVE:
            return annual_low, annual_high, f"{period}_reported"
        # otherwise fall through to inference from the size of the number

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
