"""The skills vocabulary: canonical skill names, their categories and alternative spellings.

One shared list drives the labelling tool's autocomplete and the rules-based extractor, so the gold
set and the extractor speak the same names. `vocabulary.json` is a starting point, not a complete
list: skills a labeller types that are not in it are the raw material for emerging-skill detection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_PATH = Path(__file__).with_name("vocabulary.json")
CATEGORIES = frozenset(
    {
        "language",
        "library",
        "ml_platform",
        "data_platform",
        "database",
        "cloud_devops",
        "web",
        "bi",
        "method",
        "practice",
    }
)


def _key(text: str) -> str:
    return " ".join(text.lower().split())


@dataclass(frozen=True)
class Skill:
    name: str
    category: str
    aliases: tuple[str, ...] = ()


class Vocabulary:
    def __init__(self, skills: list[Skill]) -> None:
        self.skills = skills
        self._lookup: dict[str, Skill] = {}
        for skill in skills:
            for text in (skill.name, *skill.aliases):
                key = _key(text)
                if key in self._lookup and self._lookup[key] is not skill:
                    raise ValueError(
                        f"{text!r} is used by both {self._lookup[key].name!r} and {skill.name!r}"
                    )
                self._lookup[key] = skill

    def canonical(self, text: str) -> str | None:
        """The canonical name for a name or alias (case-insensitive), or None if unknown."""
        skill = self._lookup.get(_key(text))
        return skill.name if skill else None

    def get(self, text: str) -> Skill | None:
        """The Skill for a name or alias (case-insensitive), or None if unknown."""
        return self._lookup.get(_key(text))

    def __contains__(self, text: str) -> bool:
        return _key(text) in self._lookup

    def __len__(self) -> int:
        return len(self.skills)

    def to_records(self) -> list[dict]:
        return [
            {"name": s.name, "category": s.category, "aliases": list(s.aliases)}
            for s in self.skills
        ]


def load(path: Path = DEFAULT_PATH) -> Vocabulary:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Vocabulary(
        [
            Skill(name, entry["category"], tuple(entry.get("aliases", [])))
            for name, entry in raw.items()
        ]
    )


@lru_cache(maxsize=1)
def default() -> Vocabulary:
    return load()
