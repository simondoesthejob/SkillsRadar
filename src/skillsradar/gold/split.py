"""A fixed split of the gold set into a development half and a test half.

Tune the extractor on **dev** (look at its errors, adjust rules, add vocabulary). Quote the **test**
score only once, at the end, from a version you stopped changing: that number says how the extractor
does on postings it was never tuned to. The split depends only on the posting ID and a seed, so it
never changes as the gold set grows, and a posting never moves between halves.
"""

from __future__ import annotations

import hashlib

TEST_PERCENT = 50


def split_of(posting_id: str, seed: int = 1) -> str:
    bucket = int(hashlib.sha1(f"split:{seed}:{posting_id}".encode()).hexdigest(), 16) % 100
    return "test" if bucket < TEST_PERCENT else "dev"
