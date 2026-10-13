variable "region" {
  type    = string
  default = "eu-west-2"
}

variable "name_prefix" {
  type    = string
  default = "skillsradar"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "bootstrap_users" {
  description = "Existing IAM users to place in the temporary bootstrap group. Set back to [] and re-apply once the bootstrap has succeeded."
  type        = list(string)
  default     = []
}

variable "operator_users" {
  description = "Existing IAM users to place in the standing operator group."
  type        = list(string)
  default     = []
}

variable "require_mfa" {
  type    = bool
  default = false
}
