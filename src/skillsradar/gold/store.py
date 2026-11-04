"""The gold set on disk: the sample (JSONL, one posting per line) and the labels (JSONL).

Labels are rewritten whole through a temporary file and an atomic rename, so a crash or a power cut
cannot leave a half-written file. The file is small (hundreds of lines), so this is simple and safe.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATUSES = ("done", "skip")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """Write atomically: temp file in the same folder, then rename over the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class LabelStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._labels: dict[str, dict[str, Any]] = {r["id"]: r for r in read_jsonl(path)}

    def all(self) -> dict[str, dict[str, Any]]:
        return dict(self._labels)

    def upsert(
        self,
        posting_id: str,
        skills: list[str],
        status: str = "done",
        notes: str = "",
        now: datetime | None = None,
        rejected: list[str] | None = None,
        review_added: list[str] | None = None,
        reviewed: bool | None = None,
    ) -> dict[str, Any]:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        seen: set[str] = set()
        clean = []
        for skill in skills:
            text = " ".join(str(skill).split())
            if text and text.lower() not in seen:
                seen.add(text.lower())
                clean.append(text)
        previous = self._labels.get(posting_id)
        record = {
            "id": posting_id,
            "status": status,
            "skills": clean if status == "done" else [],
            "notes": notes.strip(),
            "labelled_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
            "revisions": (previous["revisions"] + 1) if previous else 0,
        }
        # Review fields: `rejected` are extractor suggestions you judged wrong (confirmed false
        # positives), `review_added` are labels you added after seeing a suggestion (so they can be
        # reported separately), `reviewed` takes the posting off the review queue. Leaving one out
        # keeps what was saved before.
        if status == "done":
            for key, value in (
                ("rejected", rejected),
                ("review_added", review_added),
                ("reviewed", reviewed),
            ):
                value = value if value is not None else (previous or {}).get(key)
                if key == "review_added" and value:
                    value = [v for v in value if v.lower() in seen]  # still labelled
                if value:
                    record[key] = value
        self._labels[posting_id] = record
        write_jsonl(self.path, list(self._labels.values()))
        return record
