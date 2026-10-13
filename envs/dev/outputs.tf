output "bucket_names" {
  value = module.data.bucket_names
}

output "ingest_function_name" {
  value = module.ingest.function_name
}

output "adzuna_secret_arn" {
  value = module.ingest.adzuna_secret_arn
}

output "reed_secret_arn" {
  value = module.ingest.reed_secret_arn
}
