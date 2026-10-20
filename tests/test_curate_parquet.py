import io
from datetime import date

import pytest

pq = pytest.importorskip("pyarrow.parquet")

from skillsradar.curate.parquet import to_parquet_bytes  # noqa: E402
from skillsradar.curate.schema import COLUMNS  # noqa: E402


def row(**overrides):
    base = {name: None for name, _ in COLUMNS}
    base.update(
        source_id="1",
        dedupe_key="reed:1",
        title="Data Engineer",
        posted_date=date(2026, 10, 16),
        salary_is_predicted=False,
        description_truncated=False,
        observed_count=1,
    )
    return {**base, **overrides}


def test_round_trip_keeps_values_and_types():
    data = to_parquet_bytes([row(), row(source_id="2", salary_min=45000.0, remote=True)])
    table = pq.read_table(io.BytesIO(data))
    assert table.column_names == [name for name, _ in COLUMNS]
    assert table.num_rows == 2
    assert table.column("posted_date").to_pylist()[0] == date(2026, 10, 16)
    assert table.column("salary_min").to_pylist() == [None, 45000.0]
    assert table.column("remote").to_pylist() == [None, True]
    assert str(table.schema.field("observed_count").type) == "int32"


def test_empty_input_gives_a_valid_empty_file():
    table = pq.read_table(io.BytesIO(to_parquet_bytes([])))
    assert table.num_rows == 0
    assert len(table.column_names) == len(COLUMNS)
