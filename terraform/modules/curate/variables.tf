variable "name_prefix" {
  type = string
}

variable "source_dir" {
  description = "Directory zipped into the Lambda package (the Python source root, i.e. ../../src)."
  type        = string
}

variable "raw_bucket_name" {
  type = string
}

variable "raw_bucket_arn" {
  type = string
}

variable "curated_bucket_name" {
  type = string
}

variable "curated_bucket_arn" {
  type = string
}

variable "pandas_layer_arn" {
  description = "AWS SDK for pandas managed layer (provides pyarrow). Must be for the same region, Python version and CPU architecture as the function."
  type        = string
}

variable "max_reject_ratio" {
  description = "Fail the run (and trip the alarm) when more than this share of a source's records are rejected."
  type        = number
  default     = 0.05
}
