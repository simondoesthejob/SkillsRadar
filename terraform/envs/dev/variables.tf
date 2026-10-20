variable "region" {
  type    = string
  default = "eu-west-2"
}

variable "ingest_schedule_enabled" {
  type    = bool
  default = true
}

variable "pandas_layer_arn" {
  description = "AWS SDK for pandas managed layer for the curation Lambda (provides pyarrow). Pick the Python 3.12, x86_64 ARN for eu-west-2 from the AWS SDK for pandas docs."
  type        = string
  default     = "arn:aws:lambda:eu-west-2:336392948345:layer:AWSSDKPandas-Python312:31"
}
