// Reed enrichment: fetch each new Reed posting's full description once and cache it in the raw
// bucket under enriched/reed/. The curation Lambda reads the cache. Runs on demand for now;
// Step Functions will call it between ingestion and curation later.

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.root}/.build/enrich.zip"
  excludes    = ["**/__pycache__/**", "**/*.pyc", "*.egg-info/**"]
}

resource "aws_cloudwatch_log_group" "enrich" {
  name              = "/aws/lambda/${var.name_prefix}-enrich"
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
  name               = "${var.name_prefix}-enrich-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid       = "ListRawAndCache"
    actions   = ["s3:ListBucket"]
    resources = [var.raw_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["raw/*", "enriched/*"]
    }
  }

  statement {
    sid       = "ReadRawData"
    actions   = ["s3:GetObject"]
    resources = ["${var.raw_bucket_arn}/raw/*"]
  }

  statement {
    sid       = "WriteCache"
    actions   = ["s3:PutObject"]
    resources = ["${var.raw_bucket_arn}/enriched/*"]
  }

  statement {
    sid       = "ReadReedKey"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.reed_secret_arn]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.enrich.arn}:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "enrich"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_lambda_function" "enrich" {
  function_name    = "${var.name_prefix}-enrich"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "skillsradar.enrich.handler.lambda_handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 600
  memory_size      = 256

  environment {
    variables = {
      RAW_BUCKET               = var.raw_bucket_name
      REED_SECRET_ARN          = var.reed_secret_arn
      MAX_NEW                  = tostring(var.max_new_per_run)
      LOOKBACK_DAYS            = tostring(var.lookback_days)
      REQUEST_INTERVAL_SECONDS = tostring(var.request_interval_seconds)
    }
  }

  depends_on = [aws_cloudwatch_log_group.enrich, aws_iam_role_policy.lambda]
}

resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = "${var.name_prefix}-enrich-errors"
  alarm_description   = "The Reed enrichment Lambda failed, was rate limited, or hit repeated errors."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.enrich.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}
