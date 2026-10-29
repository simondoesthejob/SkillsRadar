"""Turn one day of raw records for one source into curated rows.

Steps: validate (reject what cannot be trusted), de-duplicate within the day on `dedupe_key`
(keeping the most recently ingested copy), remove personal contact details, parse Hacker News
headers, normalise salary, flag truncated descriptions. Full descriptions cached by the enrich
Lambda replace the truncated search text when available. Cross-source de-duplication is a later
step.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from skillsradar.curate import hn, rules, salary, text


@dataclass
class CurationResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)  # {"reasons": [...], "record": {}}
    stats: dict[str, Any] = field(default_factory=dict)


def _dedupe_key(record: dict[str, Any]) -> str:
    return record.get("dedupe_key") or f"{record.get('source')}:{record.get('source_id')}"


def _curate_one(
    record: dict[str, Any],
    source: str,
    copies: list[dict[str, Any]],
    curated_at: datetime,
    detail: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], Counter]:
    counts: Counter = Counter()

    # A cached full description (HTML from the source's detail endpoint) beats the truncated
    # search-result text. A detail marked "gone" (the posting was removed) is ignored.
    full_text = ""
    if detail and not detail.get("gone"):
        full_text = text.html_to_text(str(detail.get("jobDescription") or ""))
    if full_text:
        counts["descriptions_enriched"] += 1

    title, pii_title = text.strip_pii(str(record["title"]).strip())
    description, pii_desc = text.strip_pii(full_text or str(record["description"]).strip())
    counts["emails_removed"] += pii_title["emails"] + pii_desc["emails"]
    counts["phones_removed"] += pii_title["phones"] + pii_desc["phones"]

    location = record.get("location")
    remote = None
    if source == "hn_hiring":
        header_location, remote = hn.parse_header(str(record["title"]))
        location = location or header_location
        if location:
            counts["hn_location_found"] += 1

    low, high = record.get("salary_min"), record.get("salary_max")
    predicted = bool(record.get("salary_predicted"))
    period = None
    if detail and not detail.get("gone") and detail.get("salaryType"):
        slug = re.sub(r"[^a-z0-9]+", "_", str(detail["salaryType"]).lower()).strip("_")
        counts[f"salary_type_{slug}"] += 1
        period = salary.parse_period(str(detail["salaryType"]))
    annual_low, annual_high, basis = salary.normalise_salary(low, high, predicted, period)
    if period and basis and not basis.endswith("_reported") and basis != "predicted":
        counts["salary_period_conflict"] += 1  # stated period did not fit the figures
    if low is not None and high is not None and low > high:
        counts["salary_range_swapped"] += 1
    if basis:
        counts[f"salary_basis_{basis}"] += 1

    posted = record.get("posted_at")
    posted_date = rules.parse_posted_date(posted)
    if posted and posted_date is None:
        counts["posted_at_unparseable"] += 1

    truncated = False if full_text else rules.is_truncated(source, description or "")
    if truncated:
        counts["truncated_descriptions"] += 1

    ingested = sorted(str(c.get("ingested_at") or "") for c in copies)
    row = {
        "source_id": str(record["source_id"]),
        "dedupe_key": _dedupe_key(record),
        "title": title,
        "company": record.get("company") or None,
        "location": location or None,
        "remote": remote,
        "description": description,
        "description_truncated": truncated,
        "url": record.get("url") or None,
        "posted_date": posted_date,
        "salary_min": low,
        "salary_max": high,
        "salary_is_predicted": predicted,
        "salary_annual_min": annual_low,
        "salary_annual_max": annual_high,
        "salary_basis": basis,
        "category": record.get("category") or None,
        "contract_type": record.get("contract_type") or None,
        "observed_count": len(copies),
        "first_ingested_at": ingested[0] or None,
        "last_ingested_at": ingested[-1] or None,
        "curated_at": curated_at.isoformat(),
    }
    return row, counts


def curate_day(
    records: Iterable[dict[str, Any]],
    source: str,
    curated_at: datetime,
    enriched: Mapping[str, Mapping[str, Any]] | None = None,
) -> CurationResult:
    result = CurationResult()
    counts: Counter = Counter()
    groups: dict[str, list[dict[str, Any]]] = {}
    rejected_by_reason: Counter = Counter()
    rows_in = 0

    for record in records:
        rows_in += 1
        reasons = rules.hard_failures(record, source)
        if reasons:
            result.rejected.append({"reasons": reasons, "record": record})
            rejected_by_reason.update(reasons)
            continue
        groups.setdefault(_dedupe_key(record), []).append(record)

    for copies in groups.values():
        latest = max(copies, key=lambda r: str(r.get("ingested_at") or ""))
        detail = (enriched or {}).get(str(latest["source_id"]))
        row, row_counts = _curate_one(latest, source, copies, curated_at, detail)
        result.rows.append(row)
        counts.update(row_counts)

    valid = sum(len(c) for c in groups.values())
    result.stats = {
        "source": source,
        "rows_in": rows_in,
        "rows_rejected": len(result.rejected),
        "rows_valid": valid,
        "rows_out": len(result.rows),
        "duplicates_removed": valid - len(result.rows),
        "rejected_by_reason": dict(rejected_by_reason),
        **dict(counts),
    }
    return result
