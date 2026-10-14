variable "region" {
  type    = string
  default = "eu-west-2"
}

variable "name_prefix" {
  type    = string
  default = "skillsradar"
}

variable "github_repo" {
  description = "GitHub repository as owner/name, e.g. your-user/skills-radar."
  type        = string
  default = "skillsradar/skills-radar"
}

variable "create_oidc_provider" {
  type    = bool
  default = true
}
