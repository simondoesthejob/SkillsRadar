// IAM groups for the person who deploys the project from their own machine.
//
// - bootstrap group: temporary. Can create the state bucket, the GitHub OIDC provider and the
//   project's roles, and can apply the dev stack locally. Because it can create roles with
//   arbitrary permissions, treat it as admin-equivalent while anyone is a member (see
//   docs/iam-access.md). Empty it once the bootstrap has succeeded.
// - operator group: standing. Can only set the API secrets, invoke the ingest function and read
//   the environment's data, logs and dead-letter queue.
//
// Phase 1 only: later phases (Glue, Athena, SageMaker, Step Functions...) need more statements.

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  prefix     = var.name_prefix
  env_prefix = "${var.name_prefix}-${var.environment}"

  // ARN patterns for everything named <prefix>-*
  bucket_arn   = "arn:${local.partition}:s3:::${local.prefix}-*"
  role_arn     = "arn:${local.partition}:iam::${local.account_id}:role/${local.prefix}-*"
  oidc_arn     = "arn:${local.partition}:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com"
  lambda_arn   = "arn:${local.partition}:lambda:*:${local.account_id}:function:${local.prefix}-*"
  log_arn      = "arn:${local.partition}:logs:*:${local.account_id}:log-group:/aws/lambda/${local.prefix}-*"
  queue_arn    = "arn:${local.partition}:sqs:*:${local.account_id}:${local.prefix}-*"
  secret_arn   = "arn:${local.partition}:secretsmanager:*:${local.account_id}:secret:${local.prefix}-*"
  schedule_arn = "arn:${local.partition}:scheduler:*:${local.account_id}:schedule/default/${local.prefix}-*"
  alarm_arn    = "arn:${local.partition}:cloudwatch:*:${local.account_id}:alarm:${local.prefix}-*"

  // ARN patterns for the operator's environment only, named <prefix>-<environment>-*
  env_bucket_arn = "arn:${local.partition}:s3:::${local.env_prefix}-*"
  env_lambda_arn = "arn:${local.partition}:lambda:*:${local.account_id}:function:${local.env_prefix}-*"
  env_log_arn    = "arn:${local.partition}:logs:*:${local.account_id}:log-group:/aws/lambda/${local.env_prefix}-*"
  env_queue_arn  = "arn:${local.partition}:sqs:*:${local.account_id}:${local.env_prefix}-*"
  env_secret_arn = "arn:${local.partition}:secretsmanager:*:${local.account_id}:secret:${local.env_prefix}/*"
}

# ---------------------------------------------------------------------------------------------
# Bootstrap group
# ---------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "bootstrap" {
  statement {
    sid       = "ProjectBuckets"
    actions   = ["s3:*"]
    resources = [local.bucket_arn, "${local.bucket_arn}/*"]
  }

  statement {
    sid = "GithubOidcProvider"
    actions = [
      "iam:CreateOpenIDConnectProvider",
      "iam:DeleteOpenIDConnectProvider",
      "iam:GetOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint",
      "iam:AddClientIDToOpenIDConnectProvider",
      "iam:RemoveClientIDFromOpenIDConnectProvider",
      "iam:TagOpenIDConnectProvider",
      "iam:UntagOpenIDConnectProvider",
      "iam:ListOpenIDConnectProviderTags",
    ]
    resources = [local.oidc_arn]
  }

  statement {
    sid       = "FindExistingOidcProvider"
    actions   = ["iam:ListOpenIDConnectProviders"]
    resources = ["*"]
  }

  statement {
    sid = "ProjectRoles"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:GetRole",
      "iam:UpdateRole",
      "iam:UpdateRoleDescription",
      "iam:UpdateAssumeRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:ListRoleTags",
      "iam:PutRolePolicy",
      "iam:GetRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:ListRolePolicies",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
    ]
    resources = [local.role_arn]
  }

  statement {
    sid       = "PassProjectRolesToLambdaAndScheduler"
    actions   = ["iam:PassRole"]
    resources = [local.role_arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["lambda.amazonaws.com", "scheduler.amazonaws.com"]
    }
  }

  statement {
    sid       = "IngestLambda"
    actions   = ["lambda:*"]
    resources = [local.lambda_arn]
  }

  statement {
    sid = "IngestLogGroup"
    actions = [
      "logs:CreateLogGroup",
      "logs:DeleteLogGroup",
      "logs:PutRetentionPolicy",
      "logs:DeleteRetentionPolicy",
      "logs:TagResource",
      "logs:UntagResource",
      "logs:ListTagsForResource",
      "logs:TagLogGroup",
      "logs:UntagLogGroup",
      "logs:ListTagsLogGroup",
    ]
    resources = [local.log_arn, "${local.log_arn}:*"]
  }

  statement {
    sid       = "ListLogGroups"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"]
  }

  statement {
    sid       = "DeadLetterQueue"
    actions   = ["sqs:*"]
    resources = [local.queue_arn]
  }

  statement {
    sid       = "ApiSecrets"
    actions   = ["secretsmanager:*"]
    resources = [local.secret_arn]
  }

  statement {
    sid       = "IngestSchedule"
    actions   = ["scheduler:*"]
    resources = [local.schedule_arn]
  }

  statement {
    sid = "Alarms"
    actions = [
      "cloudwatch:PutMetricAlarm",
      "cloudwatch:DeleteAlarms",
      "cloudwatch:TagResource",
      "cloudwatch:UntagResource",
      "cloudwatch:ListTagsForResource",
    ]
    resources = [local.alarm_arn]
  }

  statement {
    sid       = "ListAlarms"
    actions   = ["cloudwatch:DescribeAlarms"]
    resources = ["*"]
  }
}

resource "aws_iam_group" "bootstrap" {
  name = "${local.prefix}-bootstrap"
}

resource "aws_iam_policy" "bootstrap" {
  name        = "${local.prefix}-bootstrap"
  description = "Bootstrap the project and apply the dev stack locally. Phase 1 resources only."
  policy      = data.aws_iam_policy_document.bootstrap.json
}

resource "aws_iam_group_policy_attachment" "bootstrap" {
  group      = aws_iam_group.bootstrap.name
  policy_arn = aws_iam_policy.bootstrap.arn
}

resource "aws_iam_group_membership" "bootstrap" {
  count = length(var.bootstrap_users) > 0 ? 1 : 0

  name  = "${local.prefix}-bootstrap-membership"
  group = aws_iam_group.bootstrap.name
  users = var.bootstrap_users
}

# ---------------------------------------------------------------------------------------------
# Operator group
# ---------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "operator" {
  statement {
    sid       = "SetApiCredentials"
    actions   = ["secretsmanager:PutSecretValue", "secretsmanager:DescribeSecret"]
    resources = [local.env_secret_arn]
  }

  statement {
    sid       = "InvokeIngest"
    actions   = ["lambda:InvokeFunction", "lambda:GetFunction"]
    resources = [local.env_lambda_arn]
  }

  statement {
    sid       = "ReadEnvironmentData"
    actions   = ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"]
    resources = [local.env_bucket_arn, "${local.env_bucket_arn}/*"]
  }

  statement {
    sid       = "ReadIngestLogs"
    actions   = ["logs:DescribeLogStreams", "logs:GetLogEvents", "logs:FilterLogEvents"]
    resources = [local.env_log_arn, "${local.env_log_arn}:*"]
  }

  statement {
    sid       = "InspectDeadLetterQueue"
    actions   = ["sqs:GetQueueAttributes", "sqs:GetQueueUrl", "sqs:ReceiveMessage"]
    resources = [local.env_queue_arn]
  }
}

resource "aws_iam_group" "operator" {
  name = "${local.prefix}-operator"
}

resource "aws_iam_policy" "operator" {
  name        = "${local.prefix}-operator"
  description = "Day-to-day operation of one environment: set API keys, invoke ingestion, read data and logs."
  policy      = data.aws_iam_policy_document.operator.json
}

resource "aws_iam_group_policy_attachment" "operator" {
  group      = aws_iam_group.operator.name
  policy_arn = aws_iam_policy.operator.arn
}

resource "aws_iam_group_membership" "operator" {
  count = length(var.operator_users) > 0 ? 1 : 0

  name  = "${local.prefix}-operator-membership"
  group = aws_iam_group.operator.name
  users = var.operator_users
}

# ---------------------------------------------------------------------------------------------
# Optional MFA requirement, attached to both groups
# ---------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "require_mfa" {
  statement {
    sid    = "DenyAllExceptMfaSetupWithoutMfa"
    effect = "Deny"
    not_actions = [
      "iam:ChangePassword",
      "iam:CreateVirtualMFADevice",
      "iam:EnableMFADevice",
      "iam:GetUser",
      "iam:ListMFADevices",
      "iam:ListVirtualMFADevices",
      "iam:ResyncMFADevice",
      "sts:GetSessionToken",
    ]
    resources = ["*"]

    condition {
      test     = "BoolIfExists"
      variable = "aws:MultiFactorAuthPresent"
      values   = ["false"]
    }
  }
}

resource "aws_iam_policy" "require_mfa" {
  count = var.require_mfa ? 1 : 0

  name        = "${local.prefix}-require-mfa"
  description = "Deny everything except MFA self-service when the session was not authenticated with MFA."
  policy      = data.aws_iam_policy_document.require_mfa.json
}

resource "aws_iam_group_policy_attachment" "require_mfa" {
  for_each = var.require_mfa ? {
    bootstrap = aws_iam_group.bootstrap.name
    operator  = aws_iam_group.operator.name
  } : {}

  group      = each.value
  policy_arn = aws_iam_policy.require_mfa[0].arn
}
