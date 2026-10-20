// Curation: raw JSONL in the raw bucket -> validated, de-duplicated, normalised Parquet in the
// curated bucket. Runs on demand for now; Step Functions will call it after ingestion.
//
// pyarrow comes from the AWS SDK for pandas managed layer, so the package stays a plain zip of
// ./src with no build step.

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.root}/.build/curate.zip"
  excludes    = ["**/__pycache__/**", "**/*.pyc", "*.egg-info/**"]
}

resource "aws_cloudwatch_log_group" "curate" {
  name              = "/aws/lambda/${var.name_prefix}-curate"
  retention_in_days = 30
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.name_prefix}-curate-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid       = "ListRawData"
    actions   = ["s3:ListBucket"]
    resources = [var.raw_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["raw/*"]
    }
  }

  statement {
    sid       = "ReadRawData"
    actions   = ["s3:GetObject"]
    resources = ["${var.raw_bucket_arn}/raw/*"]
  }

  statement {
    sid     = "WriteCuratedData"
    actions = ["s3:PutObject"]
    resources = [
      "${var.curated_bucket_arn}/postings/*",
      "${var.curated_bucket_arn}/quarantine/*",
      "${var.curated_bucket_arn}/quality/*",
    ]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.curate.arn}:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "curate"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_lambda_function" "curate" {
  function_name    = "${var.name_prefix}-curate"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "skillsradar.curate.handler.lambda_handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  layers           = [var.pandas_layer_arn]
  timeout          = 300
  memory_size      = 1024

  environment {
    variables = {
      RAW_BUCKET       = var.raw_bucket_name
      CURATED_BUCKET   = var.curated_bucket_name
      MAX_REJECT_RATIO = tostring(var.max_reject_ratio)
    }
  }

  depends_on = [aws_cloudwatch_log_group.curate, aws_iam_role_policy.lambda]
}

resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = "${var.name_prefix}-curate-errors"
  alarm_description   = "The curation Lambda failed (code error, or too many rejected records)."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.curate.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}
