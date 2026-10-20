variable "name_prefix" {
  description = "Environment prefix, for example skillsradar-dev. Hyphens become underscores in Glue names."
  type        = string
}

variable "raw_bucket_name" {
  description = "Bucket holding raw/source=.../dt=.../*.jsonl.gz written by the ingestion Lambda."
  type        = string
}

variable "results_bucket_name" {
  description = "Bucket for Athena query results (the artifacts bucket)."
  type        = string
}

variable "sources" {
  description = "Source names that appear as source=<name> in the raw bucket."
  type        = list(string)
  default     = ["adzuna", "reed", "hn_hiring"]
}

variable "projection_start_date" {
  description = "First dt= partition Athena should consider (yyyy-MM-dd). Set to just before your first ingestion."
  type        = string
  default     = "2026-10-01"
}

variable "scan_limit_bytes" {
  description = "Per-query data scan limit; a query that would scan more is cancelled. Minimum 10 MB."
  type        = number
  default     = 1073741824 # 1 GiB
}
