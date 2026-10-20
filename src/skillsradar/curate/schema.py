"""Column layout of the curated Parquet files.

`source` and `dt` are not columns: they are the Hive partitions in the S3 path
(`postings/dt=YYYY-MM-DD/source=<name>/`). A test keeps this list identical to the Glue table in
terraform/modules/analytics.
"""

# (column name, Athena/Hive type)
COLUMNS: list[tuple[str, str]] = [
    ("source_id", "string"),
    ("dedupe_key", "string"),
    ("title", "string"),
    ("company", "string"),
    ("location", "string"),
    ("remote", "boolean"),
    ("description", "string"),
    ("description_truncated", "boolean"),
    ("url", "string"),
    ("posted_date", "date"),
    ("salary_min", "double"),
    ("salary_max", "double"),
    ("salary_is_predicted", "boolean"),
    ("salary_annual_min", "double"),
    ("salary_annual_max", "double"),
    ("salary_basis", "string"),
    ("category", "string"),
    ("contract_type", "string"),
    ("observed_count", "int"),
    ("first_ingested_at", "string"),
    ("last_ingested_at", "string"),
    ("curated_at", "string"),
]
