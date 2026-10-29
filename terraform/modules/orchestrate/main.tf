// Daily orchestration: EventBridge Scheduler -> Step Functions -> ingest, enrich, curate Lambdas.
// Failures are emailed through an SNS topic. The state machine is defined in pipeline.asl.json.tftpl
// (a unit test checks that its states are all connected).

locals {
  function_arns = [var.ingest_function_arn, var.enrich_function_arn, var.curate_function_arn]
}

resource "aws_sns_topic" "alerts" {
  name = "${var.name_prefix}-pipeline-alerts"
  // Not encrypted with the AWS-managed key: CloudWatch alarms cannot publish to a topic that uses
  // it. Messages carry error text and execution IDs only, no job data.
}

resource "aws_sns_topic_subscription" "email" {
  count = var.alert_email == "" ? 0 : 1

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

data "aws_iam_policy_document" "sfn_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn" {
  name               = "${var.name_prefix}-pipeline-sfn"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
}

data "aws_iam_policy_document" "sfn" {
  statement {
    sid       = "InvokePipelineLambdas"
    actions   = ["lambda:InvokeFunction"]
    resources = flatten([for arn in local.function_arns : [arn, "${arn}:*"]])
  }

  statement {
    sid       = "PublishAlerts"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
  }
}

resource "aws_iam_role_policy" "sfn" {
  name   = "pipeline"
  role   = aws_iam_role.sfn.id
  policy = data.aws_iam_policy_document.sfn.json
}

resource "aws_sfn_state_machine" "pipeline" {
  name     = "${var.name_prefix}-pipeline"
  role_arn = aws_iam_role.sfn.arn
  type     = "STANDARD"

  definition = templatefile("${path.module}/pipeline.asl.json.tftpl", {
    ingest_function_arn = var.ingest_function_arn
    enrich_function_arn = var.enrich_function_arn
    curate_function_arn = var.curate_function_arn
    topic_arn           = aws_sns_topic.alerts.arn
  })

  depends_on = [aws_iam_role_policy.sfn]
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
  name               = "${var.name_prefix}-pipeline-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.pipeline.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "start-pipeline"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_scheduler_schedule" "pipeline" {
  name                         = "${var.name_prefix}-pipeline"
  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = "Europe/London"
  state                        = var.schedule_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_sfn_state_machine.pipeline.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({})

    retry_policy {
      maximum_retry_attempts       = 2
      maximum_event_age_in_seconds = 3600
    }
  }

  depends_on = [aws_iam_role_policy.scheduler]
}

// Catches a pipeline that fails in a way its own error handling cannot (for example a bad
// state machine update). Step failures are already emailed by the state machine itself.
resource "aws_cloudwatch_metric_alarm" "pipeline_failed" {
  alarm_name          = "${var.name_prefix}-pipeline-failed"
  alarm_description   = "A pipeline execution ended in FAILED (a curate failure, or an error in the state machine itself)."
  namespace           = "AWS/States"
  metric_name         = "ExecutionsFailed"
  dimensions          = { StateMachineArn = aws_sfn_state_machine.pipeline.arn }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
