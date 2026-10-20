// Makes the raw JSONL files queryable with SQL, with no crawler and no manual partition upkeep.
//
//   Glue database + external table  describe the files; the table uses partition projection, so
//                                   Athena derives every source=/dt= partition from the settings
//                                   below instead of looking them up in the catalog.
//   Athena workgroup                runs the queries, caps the data scanned per query, and keeps
//                                   results (encrypted) in the artifacts bucket.
//   Named queries                   the example queries in ./queries, saved in the workgroup.

locals {
  glue_name = replace(var.name_prefix, "-", "_")
  table     = "raw_postings"

  // One entry per field of the JSON records written by src/skillsradar (JobPosting.to_record).
  // `source` is not listed here because it is a partition column (taken from the S3 path); the
  // same field inside each JSON line is simply ignored.
  columns = [
    { name = "source_id", type = "string" },
    { name = "title", type = "string" },
    { name = "company", type = "string" },
    { name = "location", type = "string" },
    { name = "description", type = "string" },
    { name = "url", type = "string" },
    { name = "posted_at", type = "string" },
    { name = "salary_min", type = "double" },
    { name = "salary_max", type = "double" },
    { name = "salary_predicted", type = "boolean" },
    { name = "category", type = "string" },
    { name = "contract_type", type = "string" },
    { name = "dedupe_key", type = "string" },
    { name = "ingested_at", type = "string" },
  ]

  queries = { for file in fileset("${path.module}/queries", "*.sql") : trimsuffix(file, ".sql") => file }
}

resource "aws_glue_catalog_database" "this" {
  name        = local.glue_name
  description = "Skills Radar job postings (${var.name_prefix})."
}

resource "aws_glue_catalog_table" "raw_postings" {
  name          = local.table
  database_name = aws_glue_catalog_database.this.name
  description   = "Raw job postings as written by the ingestion Lambda (gzipped JSON lines)."
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    EXTERNAL = "TRUE"

    "projection.enabled"          = "true"
    "projection.source.type"      = "enum"
    "projection.source.values"    = join(",", var.sources)
    "projection.dt.type"          = "date"
    "projection.dt.format"        = "yyyy-MM-dd"
    "projection.dt.range"         = "${var.projection_start_date},NOW"
    "projection.dt.interval"      = "1"
    "projection.dt.interval.unit" = "DAYS"
    "storage.location.template"   = "s3://${var.raw_bucket_name}/raw/source=$${source}/dt=$${dt}/"
  }

  partition_keys {
    name = "source"
    type = "string"
  }

  partition_keys {
    name = "dt"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${var.raw_bucket_name}/raw/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
    }

    dynamic "columns" {
      for_each = local.columns

      content {
        name = columns.value.name
        type = columns.value.type
      }
    }
  }
}

resource "aws_athena_workgroup" "this" {
  name          = var.name_prefix
  description   = "Skills Radar queries (${var.name_prefix}) with a per-query scan limit."
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.scan_limit_bytes

    result_configuration {
      output_location = "s3://${var.results_bucket_name}/athena-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}

resource "aws_athena_named_query" "this" {
  for_each = local.queries

  name        = each.key
  description = "Example query from terraform/modules/analytics/queries/${each.value}"
  workgroup   = aws_athena_workgroup.this.id
  database    = aws_glue_catalog_database.this.name
  query       = file("${path.module}/queries/${each.value}")

  depends_on = [aws_glue_catalog_table.raw_postings]
}
