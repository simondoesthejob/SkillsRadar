variable "name_prefix" {
  description = "Prefix shared by everything the project creates (buckets, roles, functions...). Policies are scoped to names starting with it."
  type        = string
  default     = "skillsradar"
}

variable "environment" {
  description = "Environment whose resources the operator group may use day to day (resources are named <name_prefix>-<environment>-*)."
  type        = string
  default     = "dev"
}

variable "bootstrap_users" {
  description = "Existing IAM users to put in the bootstrap group. Authoritative: users not listed are removed from the group. Keep this empty except while bootstrapping."
  type        = list(string)
  default     = []
}

variable "operator_users" {
  description = "Existing IAM users to put in the operator group. Authoritative: users not listed are removed from the group."
  type        = list(string)
  default     = []
}

variable "require_mfa" {
  description = "Deny everything except MFA self-service unless the session was authenticated with MFA. CLI users must then call sts get-session-token with their MFA code (see docs/iam-access.md)."
  type        = bool
  default     = false
}
