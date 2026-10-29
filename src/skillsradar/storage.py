"""Small S3 object-store wrapper shared by the curation and enrichment Lambdas.

The Protocol lets tests pass an in-memory fake instead of boto3.
"""

from __future__ import annotations

from typing import Any, Protocol


class ObjectStore(Protocol):
    def list_keys(self, bucket: str, prefix: str) -> list[str]: ...
    def read(self, bucket: str, key: str) -> bytes: ...
    def write(self, bucket: str, key: str, body: bytes) -> None: ...


class S3Store:
    def __init__(self, client: Any) -> None:
        self._s3 = client

    def list_keys(self, bucket: str, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys

    def read(self, bucket: str, key: str) -> bytes:
        return self._s3.get_object(Bucket=bucket, Key=key)["Body"].read()

    def write(self, bucket: str, key: str, body: bytes) -> None:
        self._s3.put_object(Bucket=bucket, Key=key, Body=body)


def enriched_prefix(source: str) -> str:
    return f"enriched/{source}/"


def enriched_key(source: str, source_id: str) -> str:
    """Where the full detail of one posting is cached, in the raw bucket."""
    return f"{enriched_prefix(source)}{source_id}.json.gz"
