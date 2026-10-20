"""Write curated rows as a Parquet file. The only module that needs pyarrow."""

from __future__ import annotations

import io
from typing import Any

from skillsradar.curate.schema import COLUMNS


def _arrow_type(pa: Any, athena_type: str) -> Any:
    return {
        "string": pa.string(),
        "boolean": pa.bool_(),
        "date": pa.date32(),
        "double": pa.float64(),
        "int": pa.int32(),
    }[athena_type]


def to_parquet_bytes(rows: list[dict[str, Any]]) -> bytes:
    import pyarrow as pa  # supplied by the AWS SDK for pandas Lambda layer
    import pyarrow.parquet as pq

    schema = pa.schema([pa.field(name, _arrow_type(pa, kind)) for name, kind in COLUMNS])
    columns = {name: [row.get(name) for row in rows] for name, _ in COLUMNS}
    table = pa.Table.from_pydict(columns, schema=schema)
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression="snappy")
    return buffer.getvalue()
