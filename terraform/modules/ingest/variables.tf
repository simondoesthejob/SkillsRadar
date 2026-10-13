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

variable "adzuna_country" {
  type    = string
  default = "gb"
}

variable "adzuna_queries" {
  description = "Search phrases sent to Adzuna each run. Keep runs x queries x pages within Adzuna's 250 calls/day."
  type        = list(string)
  default     = ["data scientist", "machine learning engineer", "data engineer", "software engineer python", "mlops"]
}

variable "reed_queries" {
  description = "Search phrases sent to Reed each run."
  type        = list(string)
  default     = ["data scientist", "machine learning engineer", "data engineer", "software engineer python", "mlops"]
}

variable "reed_location" {
  description = "Reed locationName filter. Empty means UK-wide."
  type        = string
  default     = ""
}

variable "schedule_expression" {
  description = "EventBridge Scheduler expression, evaluated in Europe/London."
  type        = string
  default     = "cron(0 6 * * ? *)"
}

variable "schedule_enabled" {
  description = "Set false until the Adzuna and Reed secret values have been stored."
  type        = bool
  default     = false
}

variable "secret_recovery_window_days" {
  description = "0 deletes the secret immediately on destroy (dev); use 7-30 elsewhere."
  type        = number
  default     = 0
}
