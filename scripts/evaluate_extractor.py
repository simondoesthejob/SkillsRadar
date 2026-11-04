#!/usr/bin/env python3
"""Score the rules-based skill extractor against your hand labels.

    python scripts/evaluate_extractor.py              # development half: scores and error detail
    python scripts/evaluate_extractor.py --split test # test half: scores only, no error detail
    python scripts/evaluate_extractor.py --split all  # everything (for a progress check only)

Use the dev half while tuning rules and the vocabulary. Look at the test half rarely, and only for a
version you have stopped changing. The report is also saved as data/gold/report-<split>.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from skillsradar.gold.split import split_of  # noqa: E402
from skillsradar.gold.store import read_jsonl  # noqa: E402
from skillsradar.skills import vocabulary  # noqa: E402
from skillsradar.skills.evaluate import evaluate, render_report  # noqa: E402
from skillsradar.skills.extractor import RulesExtractor  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--sample", type=Path, default=Path("data/gold/sample.jsonl"))
    parser.add_argument("--labels", type=Path, default=Path("data/gold/labels.jsonl"))
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument(
        "--without-review-added",
        action="store_true",
        help="drop labels added after seeing an extractor suggestion (a stricter set)",
    )
    args = parser.parse_args()

    postings = read_jsonl(args.sample)
    labels = {r["id"]: r for r in read_jsonl(args.labels)}
    if not postings or not labels:
        print("No sample or labels found. Run gold_sample.py and label some postings first.")
        return 1
    if args.without_review_added:
        for label in labels.values():
            added = {a.lower() for a in label.get("review_added", [])}
            label["skills"] = [x for x in label.get("skills", []) if x.lower() not in added]
    if args.split != "all":
        postings = [p for p in postings if split_of(p["id"]) == args.split]

    vocab = vocabulary.default()
    extractor = RulesExtractor(vocab)
    # Labellers see the title and the description, so the extractor does too.
    result = evaluate(
        postings,
        labels,
        lambda p: extractor.extract(f"{p.get('title') or ''}\n{p.get('description') or ''}"),
        vocab,
    )
    if result.postings == 0:
        print(f"No labelled postings in the {args.split} split yet.")
        return 1
    report = render_report(result, args.split, args.top, show_errors=args.split != "test")
    out = args.sample.parent / f"report-{args.split}.md"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"(saved to {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
