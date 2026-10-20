variable "region" {
  type    = string
  default = "eu-west-2"
}

variable "name_prefix" {
  type    = string
  default = "skillsradar"
}

variable "github_repo" {
  description = <<-EOT
    GitHub repository exactly as it appears in the OIDC token's `sub` claim, e.g.
    your-user/skills-radar. Newer repositories use an ID-qualified form such as
    your-user@123456/skills-radar@7890123; if role assumption fails with
    "Not authorized to perform sts:AssumeRoleWithWebIdentity", print the real `sub` in a
    workflow step and use that form here (without the `repo:` prefix and `:environment:...` suffix).
  EOT
  type        = string
}

variable "create_oidc_provider" {
  type    = bool
  default = true
}
