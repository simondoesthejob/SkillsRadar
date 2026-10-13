variable "region" {
  type    = string
  default = "eu-west-2"
}

variable "name_prefix" {
  description = "Must match the prefix used by terraform/bootstrap and terraform/envs/*."
  type        = string
  default     = "skillsradar"
}

variable "environments" {
  type    = list(string)
  default = ["dev"]
}

variable "require_mfa" {
  description = "Require MFA-authenticated sessions for both groups."
  type        = bool
  default     = true
}
