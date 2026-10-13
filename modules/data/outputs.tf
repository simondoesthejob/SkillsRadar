output "bucket_names" {
  description = "Map of logical name (raw, curated, artifacts) to bucket name."
  value       = { for key, bucket in aws_s3_bucket.this : key => bucket.id }
}

output "bucket_arns" {
  description = "Map of logical name to bucket ARN."
  value       = { for key, bucket in aws_s3_bucket.this : key => bucket.arn }
}
