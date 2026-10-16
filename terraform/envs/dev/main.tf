terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  // Bucket and region are supplied at init time (see backend.hcl.example and the workflows).
  backend "s3" {
    key          = "dev/terraform.tfstate"
    use_lockfile = true
    encrypt      = true
  }
}

locals {
  name_prefix = "skillsradar-dev"
}

module "data" {
  source = "../../modules/data"

  name_prefix   = local.name_prefix
  force_destroy = true
}

module "ingest" {
  source = "../../modules/ingest"

  name_prefix     = local.name_prefix
  source_dir      = "${path.root}/../../../src"
  raw_bucket_name = module.data.bucket_names["raw"]
  raw_bucket_arn  = module.data.bucket_arns["raw"]

  // Flip to true after storing the Adzuna and Reed credentials (see README, "First deployment") .
  schedule_enabled = var.ingest_schedule_enabled
}
