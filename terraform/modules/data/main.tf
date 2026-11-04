// Three private, versioned, encrypted buckets: raw landing zone, curated (cleaned) data, and
// artefacts (model files, Athena results).

locals {
  buckets = toset(["raw", "curated", "artifacts"])
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "this" {
  for_each = local.buckets

  bucket        = "${var.name_prefix}-${each.key}-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.force_destroy
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = local.buckets

  bucket                  = aws_s3_bucket.this[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = local.buckets

  bucket = aws_s3_bucket.this[each.key].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "this" {
  for_each = local.buckets

  bucket = aws_s3_bucket.this[each.key].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  for_each = local.buckets

  bucket     = aws_s3_bucket.this[each.key].id
  depends_on = [aws_s3_bucket_versioning.this]

  rule {
    id     = "housekeeping"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  // Athena query results are disposable: expire them after a week (artifacts bucket only).
  dynamic "rule" {
    for_each = each.key == "artifacts" ? [1] : []

    content {
      id     = "athena-results"
      status = "Enabled"

      filter {
        prefix = "athena-results/"
      }

      expiration {
        days = 7
      }
    }
  }
}
