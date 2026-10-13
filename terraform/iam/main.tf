// Access stack: creates the IAM groups used by the humans who deploy and run the project.
//
// Apply this ONCE, locally, with an identity that can already manage IAM (an admin you created
// for the purpose; avoid root access keys). It cannot be applied by a member of the groups it
// creates, and there is deliberately no CI workflow for it: the roles CI assumes must not be able
// to change who has access. State is local because the remote-state bucket does not exist yet.

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
      Stack     = "iam"
    }
  }
}

module "iam_groups" {
  source = "../modules/iam_groups"

  name_prefix  = var.name_prefix
  region       = var.region
  environments = var.environments
  require_mfa  = var.require_mfa
}
