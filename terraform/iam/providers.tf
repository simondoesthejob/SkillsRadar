// How Terraform connects to AWS. No credentials belong in this file or in any .tf or .tfvars file.
//
// Credentials come from the standard AWS chain: environment variables (for example the temporary
// MFA session from `aws sts get-session-token`), a named profile in ~/.aws/config (including IAM
// Identity Center / SSO profiles), or GitHub OIDC when running in CI.

variable "aws_profile" {
  description = "Named profile from ~/.aws/config. Leave null to use environment variables or the default chain (always null in CI)."
  type        = string
  default     = null
}

variable "assume_role_arn" {
  description = "Optional role to assume after authenticating. Leave null to use the credentials as they are."
  type        = string
  default     = null
}

variable "allowed_account_ids" {
  description = "Safety check: refuse to run unless the credentials belong to one of these AWS account IDs. Recommended for local runs."
  type        = list(string)
  default     = null
}

provider "aws" {
  region              = var.region
  profile             = var.aws_profile
  allowed_account_ids = var.allowed_account_ids

  dynamic "assume_role" {
    for_each = var.assume_role_arn == null ? [] : [var.assume_role_arn]

    content {
      role_arn     = assume_role.value
      session_name = "skills-radar-terraform"
    }
  }

  default_tags {
    tags = {
      Project   = "skills-radar"
      ManagedBy = "terraform"
      Stack     = "iam"
    }
  }
}
