// Applied FIRST, by an identity that already has IAM admin rights (an admin user, or an
// IAM Identity Center admin session), with local state. It creates the groups that the
// deployment user is then placed in, so it cannot be applied using those groups.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "skills-radar"
      ManagedBy = "terraform"
      Stack     = "access"
    }
  }
}

module "access" {
  source = "../modules/access"

  name_prefix     = var.name_prefix
  environment     = var.environment
  bootstrap_users = var.bootstrap_users
  operator_users  = var.operator_users
  require_mfa     = var.require_mfa
}
