#!/usr/bin/env python3
"""Draw the gold-set sample from the curated Parquet files in S3 and save it locally.

Run from the project root on your own machine (it needs your AWS credentials, boto3 and pyarrow;
`make install` provides both):

    python scripts/gold_sample.py                # 200 postings into data/gold/sample.jsonl
    python scripts/gold_sample.py --extend 50    # add 50 more, keeping the existing ones

The sample is never overwritten, because label files refer to postings by ID. The `data/` folder is
git-ignored: it holds job-listing text from the providers, which should not be republished.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from skillsradar.gold.sample import build_sample  # noqa: E402
from skillsradar.gold.store import read_jsonl, write_jsonl  # noqa: E402

KEY = re.compile(r"postings/dt=(\d{4}-\d{2}-\d{2})/source=([\w]+)/postings\.parquet$")


def read_curated_rows(bucket: str, since: str) -> list[dict]:
    import boto3
    import pyarrow.parquet as pq

    s3 = boto3.client("s3")
    rows: list[dict] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="postings/"):
        for obj in page.get("Contents", []):
            match = KEY.search(obj["Key"])
            if not match or match.group(1) < since:
                continue
            body = s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            for row in pq.read_table(io.BytesIO(body)).to_pylist():
                rows.append({**row, "dt": match.group(1), "source": match.group(2)})
    return rows


def default_bucket() -> str:
    import boto3

    account = boto3.client("sts").get_caller_identity()["Account"]
    return f"skillsradar-dev-curated-{account}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--bucket", help="curated bucket (default: skillsradar-dev-curated-<account>)"
    )
    parser.add_argument("--out", type=Path, default=Path("data/gold/sample.jsonl"))
    parser.add_argument("--days", type=int, default=14, help="how many days back to draw from")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--reed", type=int, default=120, help="postings from Reed")
    parser.add_argument("--hn", type=int, default=60, help="postings from Hacker News")
    parser.add_argument(
        "--adzuna", type=int, default=20, help="postings from Adzuna (truncated text)"
    )
    parser.add_argument(
        "--extend", type=int, metavar="N", help="add N more postings to an existing sample"
    )
    args = parser.parse_args()

    existing = read_jsonl(args.out)
    if existing and not args.extend:
        print(f"{args.out} already exists ({len(existing)} postings). Use --extend N to add more.")
        return 1
    quotas = {"reed": args.reed, "hn_hiring": args.hn, "adzuna": args.adzuna}
    if args.extend:
        total = sum(quotas.values())
        quotas = {s: max(1, round(args.extend * q / total)) for s, q in quotas.items()}

    since = (datetime.now(UTC) - timedelta(days=args.days)).strftime("%Y-%m-%d")
    bucket = args.bucket or default_bucket()
    print(f"reading curated postings since {since} from s3://{bucket} ...")
    rows = read_curated_rows(bucket, since)
    items = build_sample(rows, quotas, args.seed, exclude_ids=[i["id"] for i in existing])
    write_jsonl(args.out, existing + items)
    per_source: dict[str, int] = {}
    for item in items:
        per_source[item["source"]] = per_source.get(item["source"], 0) + 1
    print(
        f"added {len(items)} postings {per_source}; {args.out} now has {len(existing) + len(items)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
