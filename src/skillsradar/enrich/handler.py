"""Enrichment Lambda entry point (see skillsradar.enrich.reed for what it does)."""

from __future__ import annotations

import json
import logging
from typing import Any

from skillsradar.enrich import reed
from skillsradar.storage import S3Store

log = logging.getLogger()
log.setLevel(logging.INFO)


def lambda_handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    import boto3  # provided by the Lambda runtime

    settings = reed.EnrichSettings.from_env()
    secret = boto3.client("secretsmanager").get_secret_value(SecretId=settings.reed_secret_arn)
    api_key = json.loads(secret["SecretString"])["api_key"]
    summary = reed.run(event, S3Store(boto3.client("s3")), settings, reed.make_fetcher(api_key))
    log.info("enrichment summary: %s", json.dumps(summary, default=str))
    if summary["stopped_reason"] or summary["failed"]:
        # Everything fetched so far is saved; raising makes the problem visible and alarms.
        raise RuntimeError(f"enrichment incomplete: {json.dumps(summary, default=str)}")
    return summary
