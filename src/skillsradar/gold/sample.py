"""Pick postings for the hand-labelled gold set.

The aim is a varied, reproducible sample: each posting once (its latest daily snapshot), enough
text to label, spread across job families so one kind of role does not dominate, and the same
choice every time for a given seed. Adding more later with `exclude_ids` never reshuffles the
postings already chosen.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from typing import Any

# Order matters: the first matching group wins.
_GROUPS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ml_science",
        re.compile(
            r"data scien|machine learning|\bml\b|\bai\b|\bnlp\b|research scien|"
            r"applied scien|\bllm\b",
            re.IGNORECASE,
        ),
    ),
    (
        "data_engineering",
        re.compile(r"data engineer|analytics engineer|\betl\b|big data|data platform|dwh", re.I),
    ),
    ("analytics", re.compile(r"data analy|\bbi\b|business intelligence|insight|reporting", re.I)),
    (
        "devops_cloud",
        re.compile(r"devops|\bsre\b|reliability|platform engineer|cloud|infrastructure", re.I),
    ),
    (
        "software",
        re.compile(
            r"software|developer|backend|back-end|full[- ]?stack|front[- ]?end|engineer", re.I
        ),
    ),
)


def title_group(title: str) -> str:
    for name, pattern in _GROUPS:
        if pattern.search(title or ""):
            return name
    return "other"


def latest_per_posting(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per `dedupe_key`: the one from the most recent day (`dt`)."""
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["dedupe_key"]
        if key not in latest or str(row["dt"]) > str(latest[key]["dt"]):
            latest[key] = row
    return list(latest.values())


def _order(seed: int, posting_id: str) -> str:
    return hashlib.sha1(f"{seed}:{posting_id}".encode()).hexdigest()


def stratified_sample(rows: list[dict[str, Any]], n: int, seed: int) -> list[dict[str, Any]]:
    """Up to n rows, taken round-robin across title groups in a seeded, repeatable order."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in sorted(rows, key=lambda r: _order(seed, r["dedupe_key"])):
        groups.setdefault(title_group(row.get("title", "")), []).append(row)
    chosen: list[dict[str, Any]] = []
    queues = [groups[name] for name in sorted(groups)]
    while len(chosen) < n and any(queues):
        for queue in queues:
            if queue and len(chosen) < n:
                chosen.append(queue.pop(0))
    return chosen


def to_item(row: dict[str, Any]) -> dict[str, Any]:
    """The fields the labeller needs; deliberately no salary, so labelling is about the text."""
    return {
        "id": row["dedupe_key"],
        "source": row["source"],
        "dt": str(row["dt"]),
        "title": row.get("title"),
        "company": row.get("company"),
        "location": row.get("location"),
        "url": row.get("url"),
        "description": row.get("description"),
    }


def build_sample(
    rows: Iterable[dict[str, Any]],
    quotas: dict[str, int],
    seed: int = 1,
    min_chars: int = 200,
    exclude_ids: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Sample `quotas[source]` postings per source from curated rows.

    Rows with too little text to label are dropped. `exclude_ids` are postings already in the set.
    """
    excluded = set(exclude_ids)
    postings = [
        r
        for r in latest_per_posting(rows)
        if r["dedupe_key"] not in excluded and len(r.get("description") or "") >= min_chars
    ]
    items: list[dict[str, Any]] = []
    for source in sorted(quotas):
        pool = [r for r in postings if r["source"] == source]
        items.extend(to_item(r) for r in stratified_sample(pool, quotas[source], seed))
    return sorted(items, key=lambda i: _order(seed, i["id"]))  # mix sources for labelling
