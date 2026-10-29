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

  // Flip to true after storing the Adzuna and Reed credentials (see README, "First deployment").
  schedule_enabled = var.ingest_schedule_enabled
}

module "enrich" {
  source = "../../modules/enrich"

  name_prefix     = local.name_prefix
  source_dir      = "${path.root}/../../../src"
  raw_bucket_name = module.data.bucket_names["raw"]
  raw_bucket_arn  = module.data.bucket_arns["raw"]
  reed_secret_arn = module.ingest.reed_secret_arn
}

module "orchestrate" {
  source = "../../modules/orchestrate"

  name_prefix         = local.name_prefix
  ingest_function_arn = module.ingest.function_arn
  enrich_function_arn = module.enrich.function_arn
  curate_function_arn = module.curate.function_arn
  schedule_enabled    = var.pipeline_schedule_enabled
  alert_email         = var.alert_email
}

module "analytics" {
  source = "../../modules/analytics"

  name_prefix         = local.name_prefix
  raw_bucket_name     = module.data.bucket_names["raw"]
  curated_bucket_name = module.data.bucket_names["curated"]
  results_bucket_name = module.data.bucket_names["artifacts"]
}

module "curate" {
  source = "../../modules/curate"

  name_prefix         = local.name_prefix
  source_dir          = "${path.root}/../../../src"
  raw_bucket_name     = module.data.bucket_names["raw"]
  raw_bucket_arn      = module.data.bucket_arns["raw"]
  curated_bucket_name = module.data.bucket_names["curated"]
  curated_bucket_arn  = module.data.bucket_arns["curated"]
  pandas_layer_arn    = var.pandas_layer_arn
}
