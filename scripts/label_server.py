#!/usr/bin/env python3
"""Start the local gold-set labelling tool (see skillsradar.gold.server).

    python scripts/label_server.py

then open http://127.0.0.1:8765 in your browser. Stop it with Ctrl+C; labels are already saved.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from skillsradar.gold.server import make_server  # noqa: E402
from skillsradar.skills import vocabulary  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=Path("data/gold/sample.jsonl"))
    parser.add_argument("--labels", type=Path, default=Path("data/gold/labels.jsonl"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--review-test",
        action="store_true",
        help="also show extractor suggestions for the test half (this unblinds it; avoid)",
    )
    args = parser.parse_args()
    splits = ("dev", "test") if args.review_test else ("dev",)
    try:
        server = make_server(args.sample, args.labels, vocabulary.default(), args.port, splits)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    print(f"Labelling tool running: http://127.0.0.1:{server.server_address[1]}  (Ctrl+C to stop)")
    print(f"Labels are saved to {args.labels}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
