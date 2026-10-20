"""CloudWatch metrics via the Embedded Metric Format.

Printing one JSON line to stdout is enough: CloudWatch extracts the metrics from the Lambda log
stream, with no PutMetricData call, no extra permission and no extra cost per call.
"""

from __future__ import annotations

import json
import time
from typing import Any


def emf_line(
    namespace: str,
    dimensions: dict[str, str],
    metrics: dict[str, float],
    unit: str = "Count",
    now_ms: int | None = None,
) -> str:
    return json.dumps(
        {
            "_aws": {
                "Timestamp": now_ms if now_ms is not None else int(time.time() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": namespace,
                        "Dimensions": [list(dimensions)],
                        "Metrics": [{"Name": name, "Unit": unit} for name in metrics],
                    }
                ],
            },
            **dimensions,
            **metrics,
        }
    )


def quality_metrics(stats: dict[str, Any]) -> dict[str, float]:
    return {
        "RowsIn": stats.get("rows_in", 0),
        "RowsOut": stats.get("rows_out", 0),
        "RowsRejected": stats.get("rows_rejected", 0),
        "DuplicatesRemoved": stats.get("duplicates_removed", 0),
        "TruncatedDescriptions": stats.get("truncated_descriptions", 0),
    }
