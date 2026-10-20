"""Curation: raw JSONL postings in, validated, de-duplicated, normalised Parquet out.

The cleaning rules are plain Python over dicts so they can be unit-tested without AWS or pandas.
Only `parquet.py` needs pyarrow (supplied in the Lambda by the AWS SDK for pandas layer).
"""
