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

variable "reed_secret_arn" {
  description = "Secrets Manager secret holding the Reed API key ({\"api_key\": \"...\"})."
  type        = string
}

variable "max_new_per_run" {
  description = "Most postings fetched per invocation. A backlog is cleared over several runs."
  type        = number
  default     = 300
}

variable "lookback_days" {
  description = "How many recent days of raw Reed data to look at for postings not yet fetched."
  type        = number
  default     = 3
}

variable "request_interval_seconds" {
  description = "Pause between Reed calls. Reed publishes no rate limit, so keep this polite."
  type        = number
  default     = 1
}
