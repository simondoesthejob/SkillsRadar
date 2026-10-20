// Two groups for the humans who deploy and run the project:
//
//   <prefix>-bootstrap  Temporary. Runs terraform/bootstrap (state bucket, GitHub OIDC roles) and,
//                       if wanted, terraform/envs/dev from a laptop. Remove members once CI works.
//   <prefix>-operator   Standing. Stores API keys, invokes the ingest function, reads outputs and logs.
//
// Everything is scoped to resources named <prefix>-*. This is a best-effort least-privilege
// starting point and has not been run against a live account: expect to add an action or two
// the first time Terraform reports AccessDenied.

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region_acc = "${var.region}:${local.account_id}"

  env_prefixes = [for env in var.environments : "${var.name_prefix}-${env}"]

  project_bucket_arns = [
    "arn:aws:s3:::${var.name_prefix}-*",
    "arn:aws:s3:::${var.name_prefix}-*/*",
  ]
  project_role_arn = "arn:aws:iam::${local.account_id}:role/${var.name_prefix}-*"

  // Glue database names use underscores (skillsradar_dev), not hyphens.
  glue_env_names = [for prefix in local.env_prefixes : replace(prefix, "-", "_")]
  glue_prefix    = replace(var.name_prefix, "-", "_")
}

resource "aws_iam_group" "bootstrap" {
  name = "${var.name_prefix}-bootstrap"
}

resource "aws_iam_group" "operator" {
  name = "${var.name_prefix}-operator"
}

// ---------------------------------------------------------------------------------------------
// Bootstrap group, policy 1 of 2: state bucket, GitHub OIDC provider and the project's IAM roles.
// (Split in two so each managed policy stays well under the 6,144 character limit.)
// ---------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "bootstrap_foundations" {
  statement {
    sid = "ProjectBucketsIncludingTerraformState"
    actions = [
      "s3:CreateBucket",
      "s3:DeleteBucket",
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      "s3:Get*",
      "s3:List*",
      "s3:Put*",
    ]
    resources = local.project_bucket_arns
  }

  statement {
    sid = "GitHubOidcProvider"
    actions = [
      "iam:AddClientIDToOpenIDConnectProvider",
      "iam:CreateOpenIDConnectProvider",
      "iam:DeleteOpenIDConnectProvider",
      "iam:GetOpenIDConnectProvider",
      "iam:RemoveClientIDFromOpenIDConnectProvider",
      "iam:TagOpenIDConnectProvider",
      "iam:UntagOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint",
    ]
    resources = ["arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com"]
  }

  statement {
    sid       = "FindExistingOidcProviders"
    actions   = ["iam:ListOpenIDConnectProviders"]
    resources = ["*"]
  }

  statement {
    sid = "ProjectRoles"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:DeleteRolePolicy",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:ListRolePolicies",
      "iam:ListRoleTags",
      "iam:PutRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:UpdateRole",
    ]
    resources = [local.project_role_arn]
  }

  // Only the listed managed policies can be attached to the project's roles.
  statement {
    sid       = "AttachApprovedManagedPolicies"
    actions   = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"]
    resources = [local.project_role_arn]

    condition {
      test     = "ArnEquals"
      variable = "iam:PolicyARN"
      values   = var.github_oidc_managed_policy_arns
    }
  }
}

// ---------------------------------------------------------------------------------------------
// Bootstrap group, policy 2 of 2: what terraform/envs/dev creates (for applying it from a laptop).
// ---------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "dev_stack" {
  statement {
    sid       = "Lambda"
    actions   = ["lambda:*"]
    resources = ["arn:aws:lambda:${local.region_acc}:function:${var.name_prefix}-*"]
  }

  statement {
    sid = "PassRolesToLambdaAndScheduler"
    actions = [
      "iam:PassRole",
    ]
    resources = [local.project_role_arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["lambda.amazonaws.com", "scheduler.amazonaws.com"]
    }
  }

  statement {
    sid       = "DeadLetterQueue"
    actions   = ["sqs:*"]
    resources = ["arn:aws:sqs:${local.region_acc}:${var.name_prefix}-*"]
  }

  // Terraform manages the secret containers but never reads or writes secret values.
  statement {
    sid = "SecretContainers"
    actions = [
      "secretsmanager:CreateSecret",
      "secretsmanager:DeleteResourcePolicy",
      "secretsmanager:DeleteSecret",
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetResourcePolicy",
      "secretsmanager:PutResourcePolicy",
      "secretsmanager:TagResource",
      "secretsmanager:UntagResource",
      "secretsmanager:UpdateSecret",
    ]
    resources = ["arn:aws:secretsmanager:${local.region_acc}:secret:${var.name_prefix}-*"]
  }

  statement {
    sid = "Schedules"
    actions = [
      "scheduler:CreateSchedule",
      "scheduler:DeleteSchedule",
      "scheduler:GetSchedule",
      "scheduler:UpdateSchedule",
    ]
    resources = ["arn:aws:scheduler:${local.region_acc}:schedule/default/${var.name_prefix}-*"]
  }

  statement {
    sid = "Alarms"
    actions = [
      "cloudwatch:DeleteAlarms",
      "cloudwatch:ListTagsForResource",
      "cloudwatch:PutMetricAlarm",
      "cloudwatch:TagResource",
      "cloudwatch:UntagResource",
    ]
    resources = ["arn:aws:cloudwatch:${local.region_acc}:alarm:${var.name_prefix}-*"]
  }

  statement {
    sid       = "DescribeAlarmsAndLogGroups"
    actions   = ["cloudwatch:DescribeAlarms", "logs:DescribeLogGroups"]
    resources = ["*"]
  }

  statement {
    sid = "LambdaLogGroups"
    actions = [
      "logs:CreateLogGroup",
      "logs:DeleteLogGroup",
      "logs:DeleteRetentionPolicy",
      "logs:ListTagsForResource",
      "logs:ListTagsLogGroup",
      "logs:PutRetentionPolicy",
      "logs:TagLogGroup",
      "logs:TagResource",
      "logs:UntagLogGroup",
      "logs:UntagResource",
    ]
    resources = [
      "arn:aws:logs:${local.region_acc}:log-group:/aws/lambda/${var.name_prefix}-*",
      "arn:aws:logs:${local.region_acc}:log-group:/aws/lambda/${var.name_prefix}-*:*",
    ]
  }
}

// ---------------------------------------------------------------------------------------------
// Bootstrap group, policy 3: the Glue and Athena resources in modules/analytics (laptop applies).
// ---------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "bootstrap_analytics" {
  statement {
    sid = "GlueDatabaseAndTables"
    actions = [
      "glue:CreateDatabase",
      "glue:CreateTable",
      "glue:DeleteDatabase",
      "glue:DeleteTable",
      "glue:GetDatabase",
      "glue:GetTable",
      "glue:GetTags",
      "glue:TagResource",
      "glue:UntagResource",
      "glue:UpdateDatabase",
      "glue:UpdateTable",
    ]
    resources = [
      "arn:aws:glue:${local.region_acc}:catalog",
      "arn:aws:glue:${local.region_acc}:database/${local.glue_prefix}_*",
      "arn:aws:glue:${local.region_acc}:table/${local.glue_prefix}_*/*",
    ]
  }

  statement {
    sid = "AthenaWorkgroups"
    actions = [
      "athena:CreateWorkGroup",
      "athena:DeleteWorkGroup",
      "athena:GetWorkGroup",
      "athena:ListTagsForResource",
      "athena:TagResource",
      "athena:UntagResource",
      "athena:UpdateWorkGroup",
    ]
    resources = ["arn:aws:athena:${local.region_acc}:workgroup/${var.name_prefix}-*"]
  }

  // Named queries cannot be limited by resource name.
  statement {
    sid = "AthenaNamedQueries"
    actions = [
      "athena:BatchGetNamedQuery",
      "athena:CreateNamedQuery",
      "athena:DeleteNamedQuery",
      "athena:GetNamedQuery",
      "athena:ListNamedQueries",
    ]
    resources = ["*"]
  }
}

// ---------------------------------------------------------------------------------------------
// Operator group: day-to-day use once CI owns deployments. No access to Terraform state.
// ---------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "operator" {
  statement {
    sid     = "StoreApiCredentials"
    actions = ["secretsmanager:DescribeSecret", "secretsmanager:PutSecretValue"]
    resources = [
      for prefix in local.env_prefixes : "arn:aws:secretsmanager:${local.region_acc}:secret:${prefix}/*"
    ]
  }

  statement {
    sid     = "RunIngestion"
    actions = ["lambda:GetFunction", "lambda:InvokeFunction"]
    resources = [
      for prefix in local.env_prefixes : "arn:aws:lambda:${local.region_acc}:function:${prefix}-*"
    ]
  }

  statement {
    sid     = "ListEnvironmentBuckets"
    actions = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [
      for prefix in local.env_prefixes : "arn:aws:s3:::${prefix}-*"
    ]
  }

  statement {
    sid     = "ReadEnvironmentData"
    actions = ["s3:GetObject"]
    resources = [
      for prefix in local.env_prefixes : "arn:aws:s3:::${prefix}-*/*"
    ]
  }

  statement {
    sid     = "InspectDeadLetterQueue"
    actions = ["sqs:GetQueueAttributes", "sqs:GetQueueUrl", "sqs:ReceiveMessage"]
    resources = [
      for prefix in local.env_prefixes : "arn:aws:sqs:${local.region_acc}:${prefix}-*"
    ]
  }

  statement {
    sid     = "ReadLambdaLogs"
    actions = ["logs:DescribeLogStreams", "logs:FilterLogEvents", "logs:GetLogEvents"]
    resources = flatten([
      for prefix in local.env_prefixes : [
        "arn:aws:logs:${local.region_acc}:log-group:/aws/lambda/${prefix}-*",
        "arn:aws:logs:${local.region_acc}:log-group:/aws/lambda/${prefix}-*:*",
      ]
    ])
  }

  statement {
    sid       = "FindLogGroups"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"]
  }

  // Run Athena queries in the environment workgroups and read the catalog. Results are written
  // to the artifacts bucket under athena-results/.
  statement {
    sid = "RunAthenaQueries"
    actions = [
      "athena:BatchGetNamedQuery",
      "athena:GetNamedQuery",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:GetWorkGroup",
      "athena:ListNamedQueries",
      "athena:ListQueryExecutions",
      "athena:StartQueryExecution",
      "athena:StopQueryExecution",
    ]
    resources = [
      for prefix in local.env_prefixes : "arn:aws:athena:${local.region_acc}:workgroup/${prefix}"
    ]
  }

  statement {
    sid = "ReadGlueCatalog"
    actions = [
      "glue:GetDatabase",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:GetTable",
      "glue:GetTables",
    ]
    resources = flatten([
      "arn:aws:glue:${local.region_acc}:catalog",
      [for name in local.glue_env_names : "arn:aws:glue:${local.region_acc}:database/${name}"],
      [for name in local.glue_env_names : "arn:aws:glue:${local.region_acc}:table/${name}/*"],
    ])
  }

  statement {
    sid = "WriteAthenaResults"
    actions = [
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts",
      "s3:PutObject",
    ]
    resources = [
      for prefix in local.env_prefixes : "arn:aws:s3:::${prefix}-artifacts-*/athena-results/*"
    ]
  }
}

// ---------------------------------------------------------------------------------------------
// Optional: require MFA for everything except setting MFA up. Long-lived access keys carry no MFA
// context, so members must use temporary credentials from `aws sts get-session-token` (see
// docs/iam-access.md).
// ---------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "require_mfa" {
  count = var.require_mfa ? 1 : 0

  statement {
    sid = "ManageOwnMfaAndPassword"
    actions = [
      "iam:ChangePassword",
      "iam:CreateVirtualMFADevice",
      "iam:EnableMFADevice",
      "iam:GetUser",
      "iam:ListMFADevices",
      "iam:ResyncMFADevice",
    ]
    resources = [
      "arn:aws:iam::${local.account_id}:user/$${aws:username}",
      "arn:aws:iam::${local.account_id}:mfa/$${aws:username}",
    ]
  }

  statement {
    sid       = "ListVirtualMfaDevices"
    actions   = ["iam:ListVirtualMFADevices"]
    resources = ["*"]
  }

  statement {
    sid    = "DenyEverythingElseWithoutMfa"
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

// ---------------------------------------------------------------------------------------------
// Policies and attachments
// ---------------------------------------------------------------------------------------------

resource "aws_iam_policy" "bootstrap_foundations" {
  name        = "${var.name_prefix}-bootstrap-foundations"
  description = "State bucket, GitHub OIDC provider and project IAM roles."
  policy      = data.aws_iam_policy_document.bootstrap_foundations.json
}

resource "aws_iam_policy" "dev_stack" {
  name        = "${var.name_prefix}-dev-stack"
  description = "Create and manage the resources in terraform/envs/dev."
  policy      = data.aws_iam_policy_document.dev_stack.json
}

resource "aws_iam_policy" "bootstrap_analytics" {
  name        = "${var.name_prefix}-bootstrap-analytics"
  description = "Create and manage the Glue and Athena resources in modules/analytics."
  policy      = data.aws_iam_policy_document.bootstrap_analytics.json
}

resource "aws_iam_policy" "operator" {
  name        = "${var.name_prefix}-operator"
  description = "Store API keys, invoke ingestion, read data, logs and the dead-letter queue."
  policy      = data.aws_iam_policy_document.operator.json
}

resource "aws_iam_policy" "require_mfa" {
  count = var.require_mfa ? 1 : 0

  name        = "${var.name_prefix}-require-mfa"
  description = "Deny everything except MFA self-service until the session uses MFA."
  policy      = data.aws_iam_policy_document.require_mfa[0].json
}

resource "aws_iam_group_policy_attachment" "bootstrap_foundations" {
  group      = aws_iam_group.bootstrap.name
  policy_arn = aws_iam_policy.bootstrap_foundations.arn
}

resource "aws_iam_group_policy_attachment" "bootstrap_dev_stack" {
  group      = aws_iam_group.bootstrap.name
  policy_arn = aws_iam_policy.dev_stack.arn
}

resource "aws_iam_group_policy_attachment" "bootstrap_analytics" {
  group      = aws_iam_group.bootstrap.name
  policy_arn = aws_iam_policy.bootstrap_analytics.arn
}

resource "aws_iam_group_policy_attachment" "operator" {
  group      = aws_iam_group.operator.name
  policy_arn = aws_iam_policy.operator.arn
}

resource "aws_iam_group_policy_attachment" "bootstrap_mfa" {
  count = var.require_mfa ? 1 : 0

  group      = aws_iam_group.bootstrap.name
  policy_arn = aws_iam_policy.require_mfa[0].arn
}

resource "aws_iam_group_policy_attachment" "operator_mfa" {
  count = var.require_mfa ? 1 : 0

  group      = aws_iam_group.operator.name
  policy_arn = aws_iam_policy.require_mfa[0].arn
}
