"""A dictionary-and-rules skill extractor: the baseline any learned extractor must beat.

It finds every vocabulary name or alias in a posting's text, then applies a few rules so that common
English words are not mistaken for skills:

* The longest match wins where matches overlap ("Apache Spark" over "Spark", "T-SQL" over "SQL").
* Names and aliases match whole words only, ignoring case ("sql", "SQL"), with an optional plural.
* Words that are also ordinary English or single letters ("R", "Go", "Spark", "Excel", "Lambda",
  "REST", ...) must be written capitalised or in capitals, and are only accepted when the text
  around them looks technical: another confident skill nearby, or a word such as "experience",
  "skills" or "programming" close by.

Everything here is deliberately simple and inspectable, so errors found against the gold set can be
traced to one rule. It is not smart: it cannot tell "we do not use Java" from "we use Java".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from skillsradar.skills.vocabulary import Vocabulary, default

# Lower-case surface forms that need capitals AND technical context to count.
NEEDS_CONTEXT = frozenset(
    {
        "r", "c", "go", "spark", "rest", "glue", "lambda", "spring", "express", "excel", "swift",
        "oracle", "prophet", "hive", "iceberg", "presto", "synapse", "torch", "elk", "sas", "dash",
    }
)  # fmt: skip

_CONTEXT_WORDS = re.compile(
    r"\b(?:experience|experienced|skills?|knowledge|proficien\w+|programming|languages?|frameworks?|"
    r"stack|tools?|tooling|platforms?|expertise|familiar\w*|using|ability|understanding|"
    r"libraries|technolog\w+|developer|engineering)\b",
    re.IGNORECASE,
)
_WORD = r"A-Za-z0-9_"
_CONTEXT_WINDOW_SKILLS = 100  # characters either side to look for another confident skill
_CONTEXT_WINDOW_WORDS = 40  # characters either side to look for a context word


@dataclass(frozen=True)
class Match:
    skill: str
    start: int
    end: int
    text: str
    gated: bool  # was accepted only because of surrounding context


def _surface_pattern(surface: str, plural_ok: bool) -> re.Pattern[str]:
    body = r"\s+".join(re.escape(part) for part in surface.split())
    if plural_ok:
        body += "s?"
    return re.compile(rf"(?<![{_WORD}])(?:{body})(?![{_WORD}])", re.IGNORECASE)


class RulesExtractor:
    def __init__(self, vocab: Vocabulary | None = None) -> None:
        self.vocab = vocab or default()
        self._patterns: list[tuple[re.Pattern[str], str, str]] = []
        for skill in self.vocab.skills:
            for surface in {skill.name, *skill.aliases}:
                key = surface.lower()
                plural_ok = key not in NEEDS_CONTEXT and len(surface) >= 4 and surface[-1].isalpha()
                self._patterns.append((_surface_pattern(surface, plural_ok), skill.name, key))

    # -- matching ---------------------------------------------------------------------------

    @staticmethod
    def _case_ok(key: str, canonical: str, text: str) -> bool:
        """For context-gated words, the text must be capitalised or in capitals, not lower case."""
        return text in {key.upper(), key.capitalize(), canonical}

    @staticmethod
    def _letter_context_ok(text: str, start: int, end: int) -> bool:
        """Reject "R&D", "C++", "R/V" style uses of a single letter."""
        before = text[start - 1 : start]
        after = text[end : end + 1]
        return before not in {"&", "/"} and after not in {"&", "/", "+", "#"}

    def _candidates(self, text: str) -> list[Match]:
        found: list[Match] = []
        for pattern, canonical, key in self._patterns:
            for m in pattern.finditer(text):
                gated = key in NEEDS_CONTEXT
                if gated:
                    if not self._case_ok(key, canonical, m.group(0)):
                        continue
                    if len(key) == 1 and not self._letter_context_ok(text, m.start(), m.end()):
                        continue
                found.append(Match(canonical, m.start(), m.end(), m.group(0), gated))
        return found

    @staticmethod
    def _longest_first(matches: list[Match]) -> list[Match]:
        """Keep the longest of any overlapping matches."""
        kept: list[Match] = []
        for match in sorted(matches, key=lambda m: (-(m.end - m.start), m.start)):
            if all(match.end <= k.start or match.start >= k.end for k in kept):
                kept.append(match)
        return sorted(kept, key=lambda m: m.start)

    @staticmethod
    def _has_context(text: str, match: Match, confident: list[Match]) -> bool:
        lo, hi = match.start, match.end
        near = any(
            other.end >= lo - _CONTEXT_WINDOW_SKILLS and other.start <= hi + _CONTEXT_WINDOW_SKILLS
            for other in confident
        )
        if near:
            return True
        window = text[max(0, lo - _CONTEXT_WINDOW_WORDS) : hi + _CONTEXT_WINDOW_WORDS]
        return bool(_CONTEXT_WORDS.search(window))

    def find(self, text: str) -> list[Match]:
        """Every accepted match, in order of appearance (a skill can appear more than once)."""
        if not text:
            return []
        matches = self._longest_first(self._candidates(text))
        confident = [m for m in matches if not m.gated]
        return [m for m in matches if not m.gated or self._has_context(text, m, confident)]

    def extract(self, text: str) -> list[str]:
        """The distinct skills found, in order of first appearance."""
        seen: dict[str, None] = {}
        for match in self.find(text):
            seen.setdefault(match.skill, None)
        return list(seen)
