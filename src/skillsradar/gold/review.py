"""Review mode for the labeller: show where the rules extractor and your labels disagree.

For one labelled posting this works out

* **candidates**: skills the extractor found that you did not label (the ones worth a second look),
* **missed**: skills you labelled that the extractor did not find (and whether the vocabulary knows
  them at all), and
* **highlights**: where in the title and description each of those words sits.

Offsets are computed on the same text the evaluation uses (title, newline, description) so what you
review is what is scored, then converted to positions within the title or the description for the
page. Only the *disagreements* are offered as suggestions. Skills you and the extractor agree on
are highlighted quietly and never prompt you, which keeps the review about judging evidence rather
than ticking a list.
"""

from __future__ import annotations

import re
from typing import Any

from skillsradar.gold.split import split_of
from skillsradar.skills.extractor import RulesExtractor
from skillsradar.skills.vocabulary import Vocabulary

MAX_MISSED_HIGHLIGHTS = 20


def review_text(item: dict[str, Any]) -> tuple[str, str, str]:
    title, description = item.get("title") or "", item.get("description") or ""
    return title, description, f"{title}\n{description}"


def _key(skill: str) -> str:
    return " ".join(skill.lower().split())


def _field_span(title_len: int, start: int, end: int) -> tuple[str, int, int] | None:
    if end <= title_len:
        return "title", start, end
    if start > title_len:  # skip the joining newline
        offset = title_len + 1
        return "description", start - offset, end - offset
    return None  # a match straddling title and description cannot be drawn


def _plain_occurrences(text: str, surfaces: list[str]) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    for surface in surfaces:
        body = r"\s+".join(re.escape(p) for p in surface.split())
        flags = 0 if len(surface) <= 2 else re.IGNORECASE
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){body}(?![A-Za-z0-9_])", flags)
        found += [(m.start(), m.end()) for m in pattern.finditer(text)]
    return sorted(set(found))


def review_posting(
    item: dict[str, Any],
    label_skills: list[str],
    rejected: list[str],
    extractor: RulesExtractor,
    vocab: Vocabulary,
) -> dict[str, Any]:
    title, _, text = review_text(item)
    display: dict[str, str] = {}

    def canon(skill: str) -> str:
        name = vocab.canonical(skill) or skill
        display.setdefault(_key(name), name)
        return _key(name)

    gold = {canon(s) for s in label_skills}
    rejected_keys = {canon(s) for s in rejected}
    matches = extractor.find(text)
    predicted: dict[str, None] = {}
    for m in matches:
        predicted.setdefault(canon(m.skill), None)

    highlights: list[dict[str, Any]] = []
    first_index: dict[str, int] = {}
    counts: dict[str, int] = {}
    for m in matches:
        key = canon(m.skill)
        span = _field_span(len(title), m.start, m.end)
        if span is None:
            continue
        counts[key] = counts.get(key, 0) + 1
        first_index.setdefault(key, len(highlights))
        kind = "agreed" if key in gold else "candidate"
        highlights.append(
            {
                "field": span[0],
                "start": span[1],
                "end": span[2],
                "skill": display[key],
                "kind": kind,
            }
        )

    candidates = [
        {
            "skill": display[k],
            "category": (s.category if (s := vocab.get(display[k])) else None),
            "count": counts.get(k, 0),
            "first": first_index.get(k),
            "rejected": k in rejected_keys,
        }
        for k in predicted
        if k not in gold
    ]

    missed = []
    taken = [(h["field"], h["start"], h["end"]) for h in highlights]
    for key in (k for k in (canon(s) for s in label_skills) if k not in predicted):
        name = display[key]
        entry = vocab.get(name)
        known = entry is not None
        surfaces = [name, *(entry.aliases if entry else ())]
        placed = 0
        for start, end in _plain_occurrences(text, surfaces)[:MAX_MISSED_HIGHLIGHTS]:
            span = _field_span(len(title), start, end)
            if span is None or any(
                f == span[0] and span[1] < e and s < span[2] for f, s, e in taken
            ):
                continue
            taken.append(span)
            first_index.setdefault(key, len(highlights))
            highlights.append(
                {
                    "field": span[0],
                    "start": span[1],
                    "end": span[2],
                    "skill": name,
                    "kind": "missed",
                }
            )
            placed += 1
        missed.append(
            {
                "skill": name,
                "in_vocabulary": known,
                "first": first_index.get(key),
                "occurrences": placed,
            }
        )
    return {
        "candidates": candidates,
        "missed": missed,
        "agreed": sorted(display[k] for k in gold & set(predicted)),
        "highlights": highlights,
    }


def review_queue(
    items: list[dict[str, Any]],
    labels: dict[str, dict[str, Any]],
    extractor: RulesExtractor,
    vocab: Vocabulary,
    splits: tuple[str, ...] = ("dev",),
) -> list[dict[str, Any]]:
    """Labelled, not-yet-reviewed postings with at least one candidate, most disagreement first."""
    queue = []
    for item in items:
        label = labels.get(item["id"])
        if not label or label.get("status") != "done" or label.get("reviewed"):
            continue
        if split_of(item["id"]) not in splits:
            continue
        result = review_posting(item, label["skills"], label.get("rejected", []), extractor, vocab)
        pending = [c for c in result["candidates"] if not c["rejected"]]
        if pending:
            queue.append(
                {"id": item["id"], "candidates": len(pending), "missed": len(result["missed"])}
            )
    queue.sort(key=lambda q: (-q["candidates"], q["id"]))
    return queue
