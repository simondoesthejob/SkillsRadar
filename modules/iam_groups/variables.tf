variable "name_prefix" {
  description = "Project-wide prefix used in resource names (must match the bootstrap and env stacks)."
  type        = string
  default     = "skillsradar"
}

variable "region" {
  description = "Region the project's resources live in."
  type        = string
}

variable "environments" {
  description = "Environment names the operator group may work with, e.g. [\"dev\"]."
  type        = list(string)
  default     = ["dev"]
}

variable "github_oidc_managed_policy_arns" {
  description = "Managed policies the bootstrap group may attach to the project's roles. Must cover whatever the github_oidc module attaches (ReadOnlyAccess, and AdministratorAccess until the apply role is tightened)."
  type        = list(string)
  default = [
    "arn:aws:iam::aws:policy/ReadOnlyAccess",
    "arn:aws:iam::aws:policy/AdministratorAccess",
  ]
}

variable "require_mfa" {
  description = "Deny everything except MFA self-service unless the session was authenticated with MFA."
  type        = bool
  default     = true
}
