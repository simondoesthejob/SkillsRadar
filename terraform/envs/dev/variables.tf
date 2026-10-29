variable "region" {
  type    = string
  default = "eu-west-2"
}

variable "ingest_schedule_enabled" {
  description = "The original direct schedule (ingest Lambda only). Leave false: the pipeline schedule below replaces it, and keeping both would ingest twice a day."
  type        = bool
  default     = false
}

variable "pipeline_schedule_enabled" {
  description = "Daily 06:00 London run of the whole pipeline (ingest, enrich, curate). Needs the Adzuna and Reed secrets stored."
  type        = bool
  default     = true
}

variable "alert_email" {
  description = "Where pipeline failure emails go. Supplied by CI from the ALERT_EMAIL repository variable, so the address is not committed. Empty means no subscriber."
  type        = string
  default     = ""
}

variable "pandas_layer_arn" {
  description = "AWS SDK for pandas managed layer for the curation Lambda (provides pyarrow). Pick the Python 3.12, x86_64 ARN for eu-west-2 from the AWS SDK for pandas docs."
  type        = string
  default     = "arn:aws:lambda:eu-west-2:336392948345:layer:AWSSDKPandas-Python312:31"
}
