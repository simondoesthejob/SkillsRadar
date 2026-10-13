// Scheduled ingestion: EventBridge Scheduler -> Lambda -> S3 raw bucket.
// Failures land in an SQS dead-letter queue and raise a CloudWatch alarm.

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.root}/.build/ingest.zip"
  excludes    = ["**/__pycache__/**", "**/*.pyc", "*.egg-info/**"]
}

resource "aws_secretsmanager_secret" "adzuna" {
  name                    = "${var.name_prefix}/adzuna"
  description             = "Adzuna API credentials as JSON: {\"app_id\": \"...\", \"app_key\": \"...\"}. Value is set out of band."
  recovery_window_in_days = var.secret_recovery_window_days
}

resource "aws_secretsmanager_secret" "reed" {
  name                    = "${var.name_prefix}/reed"
  description             = "Reed Jobseeker API key as JSON: {\"api_key\": \"...\"}. Value is set out of band."
  recovery_window_in_days = var.secret_recovery_window_days
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name_prefix}-ingest-dlq"
  message_retention_seconds = 1209600 # 14 days
  sqs_managed_sse_enabled   = true
}

resource "aws_cloudwatch_log_group" "ingest" {
  name              = "/aws/lambda/${var.name_prefix}-ingest"
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
  name               = "${var.name_prefix}-ingest-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid       = "WriteRawData"
    actions   = ["s3:PutObject"]
    resources = ["${var.raw_bucket_arn}/raw/*"]
  }

  statement {
    sid       = "ReadApiCredentials"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.adzuna.arn, aws_secretsmanager_secret.reed.arn]
  }

  statement {
    sid       = "DeadLetter"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.dlq.arn]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.ingest.arn}:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "ingest"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_lambda_function" "ingest" {
  function_name    = "${var.name_prefix}-ingest"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "skillsradar.handler.lambda_handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 180
  memory_size      = 256

  dead_letter_config {
    target_arn = aws_sqs_queue.dlq.arn
  }

  environment {
    variables = {
      RAW_BUCKET        = var.raw_bucket_name
      ADZUNA_SECRET_ARN = aws_secretsmanager_secret.adzuna.arn
      ADZUNA_COUNTRY    = var.adzuna_country
      ADZUNA_QUERIES    = join(",", var.adzuna_queries)
      REED_SECRET_ARN   = aws_secretsmanager_secret.reed.arn
      REED_QUERIES      = join(",", var.reed_queries)
      REED_LOCATION     = var.reed_location
    }
  }

  depends_on = [aws_cloudwatch_log_group.ingest, aws_iam_role_policy.lambda]
}

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.name_prefix}-ingest-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.ingest.arn]
  }

  statement {
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.dlq.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "invoke-ingest"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_scheduler_schedule" "ingest" {
  name                         = "${var.name_prefix}-ingest"
  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = "Europe/London"
  state                        = var.schedule_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.ingest.arn
    role_arn = aws_iam_role.scheduler.arn

    retry_policy {
      maximum_retry_attempts       = 2
      maximum_event_age_in_seconds = 3600
    }

    dead_letter_config {
      arn = aws_sqs_queue.dlq.arn
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "dlq_not_empty" {
  alarm_name          = "${var.name_prefix}-ingest-dlq-not-empty"
  alarm_description   = "A scheduled ingestion run failed and landed in the dead-letter queue."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.dlq.name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}
