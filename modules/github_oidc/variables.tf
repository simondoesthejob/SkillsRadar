variable "name_prefix" {
  type = string
}

variable "github_repo" {
  description = "GitHub repository allowed to assume the roles, as owner/name."
  type        = string
}

variable "state_bucket_arn" {
  type = string
}

variable "apply_environment" {
  description = "GitHub environment whose jobs may assume the apply role."
  type        = string
  default     = "dev"
}

variable "create_oidc_provider" {
  description = "Set false if the account already has a GitHub OIDC provider (only one per URL is allowed)."
  type        = bool
  default     = true
}

variable "apply_policy_arns" {
  description = "Managed policies attached to the apply role. Tighten before using beyond a personal sandbox."
  type        = list(string)
  default     = ["arn:aws:iam::aws:policy/AdministratorAccess"]
}
