"""Score extracted skills against hand-labelled postings.

Scores are skill-level, per posting: a skill is a true positive if it is both predicted and labelled
for that posting. Precision is TP / (TP + FP), recall is TP / (TP + FN), F1 is their harmonic mean,
and the headline numbers are *micro* averages (all postings pooled), so postings with many skills
count for more.

Two recall figures are reported because they answer different questions:

* **recall** counts every labelled skill. A skill that is not in the vocabulary can never be
  found by a vocabulary-based extractor, so this number includes that ceiling.
* **in-vocabulary recall** counts only labelled skills the vocabulary knows. It isolates matching
  errors (rules that miss or reject a skill they should find) from coverage gaps.

The labelled skills that are *not* in the vocabulary are listed as vocabulary gaps. Those are the
candidates to add, and the seed of emerging-skill detection.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from skillsradar.skills.vocabulary import Vocabulary


def _norm(skill: str) -> str:
    return " ".join(skill.lower().split())


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, other: Counts) -> None:
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn

    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        return (
            2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
        )


@dataclass
class Evaluation:
    postings: int = 0
    overall: Counts = field(default_factory=Counts)
    in_vocab: Counts = field(default_factory=Counts)  # fn limited to labelled skills in vocabulary
    by_source: dict[str, Counts] = field(default_factory=dict)
    per_skill: dict[str, Counts] = field(default_factory=dict)
    vocabulary_gaps: Counter = field(default_factory=Counter)
    errors: list[dict[str, Any]] = field(default_factory=list)  # per posting, for inspection


def evaluate(
    postings: Iterable[dict[str, Any]],
    labels: dict[str, dict[str, Any]],
    predict: Callable[[dict[str, Any]], list[str]],
    vocab: Vocabulary,
) -> Evaluation:
    """Compare `predict(posting)` with the labels for every posting that has a finished label."""
    result = Evaluation()
    display: dict[str, str] = {}

    def canonical(skill: str) -> str:
        name = vocab.canonical(skill) or skill
        display.setdefault(_norm(name), name)
        return _norm(name)

    for posting in postings:
        label = labels.get(posting["id"])
        if not label or label.get("status") != "done":
            continue
        gold = {canonical(s) for s in label["skills"]}
        predicted = {canonical(s) for s in predict(posting)}
        known_gold = {s for s in gold if s in vocab}

        counts = Counts(len(gold & predicted), len(predicted - gold), len(gold - predicted))
        vocab_counts = Counts(
            len(known_gold & predicted), len(predicted - gold), len(known_gold - predicted)
        )
        result.postings += 1
        result.overall.add(counts)
        result.in_vocab.add(vocab_counts)
        result.by_source.setdefault(posting["source"], Counts()).add(counts)
        for skill in gold | predicted:
            slot = result.per_skill.setdefault(skill, Counts())
            slot.tp += skill in gold and skill in predicted
            slot.fp += skill in predicted and skill not in gold
            slot.fn += skill in gold and skill not in predicted
        for skill in gold - known_gold:
            result.vocabulary_gaps[skill] += 1
        if predicted != gold:
            result.errors.append(
                {
                    "id": posting["id"],
                    "source": posting["source"],
                    "title": posting.get("title"),
                    "missed": sorted(display[s] for s in gold - predicted),
                    "extra": sorted(display[s] for s in predicted - gold),
                }
            )
    result.per_skill = {display[k]: v for k, v in result.per_skill.items()}
    result.vocabulary_gaps = Counter({display[k]: v for k, v in result.vocabulary_gaps.items()})
    return result


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def _row(name: str, c: Counts) -> str:
    return (
        f"| {name} | {c.tp} | {c.fp} | {c.fn} | {_pct(c.precision)} | {_pct(c.recall)} | "
        f"{_pct(c.f1)} |"
    )


def render_report(
    ev: Evaluation, split: str, top: int = 15, show_errors: bool = True, max_errors: int = 25
) -> str:
    """A Markdown report. Postings in the test split should be reported without error detail."""
    head = "| | TP | FP | FN | Precision | Recall | F1 |\n|---|---|---|---|---|---|---|"
    lines = [
        f"# Skill extractor evaluation ({split})",
        "",
        f"{ev.postings} labelled postings, {ev.overall.tp + ev.overall.fn} labelled skills.",
        "",
        head,
        _row("**All skills (micro)**", ev.overall),
        _row("In-vocabulary labels only", ev.in_vocab),
    ]
    if ev.by_source:
        lines += ["", "## By source", "", head]
        lines += [_row(src, c) for src, c in sorted(ev.by_source.items())]
    if not show_errors:
        lines += [
            "",
            "Error detail is hidden for the test split so the extractor is not tuned to it.",
        ]
        return "\n".join(lines) + "\n"

    def worst(key: Callable[[tuple[str, Counts]], int]) -> list[tuple[str, Counts]]:
        ranked = sorted(ev.per_skill.items(), key=lambda kv: (-key(kv), kv[0].lower()))
        return [kv for kv in ranked if key(kv) > 0][:top]

    lines += ["", "## Skills most often wrongly found (false positives)", ""]
    lines += [f"- **{name}**: {c.fp} wrong, {c.tp} right" for name, c in worst(lambda kv: kv[1].fp)]
    lines += ["", "## Skills most often missed (false negatives)", ""]
    lines += [
        f"- **{name}**: {c.fn} missed, {c.tp} found" for name, c in worst(lambda kv: kv[1].fn)
    ]
    lines += ["", "## Vocabulary gaps (labelled, but not in the vocabulary)", ""]
    gaps = ev.vocabulary_gaps.most_common(top * 2)
    lines += [f"- {name}: {n} posting{'s' if n != 1 else ''}" for name, n in gaps] or ["- none"]
    lines += ["", f"## Postings with errors (first {max_errors})", ""]
    for err in ev.errors[:max_errors]:
        lines.append(f"- `{err['id']}` ({err['source']}) {err['title']}")
        if err["missed"]:
            lines.append(f"  - missed: {', '.join(err['missed'])}")
        if err["extra"]:
            lines.append(f"  - extra: {', '.join(err['extra'])}")
    return "\n".join(lines) + "\n"
