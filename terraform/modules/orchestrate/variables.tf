variable "name_prefix" {
  type = string
}

variable "ingest_function_arn" {
  type = string
}

variable "enrich_function_arn" {
  type = string
}

variable "curate_function_arn" {
  type = string
}

variable "schedule_expression" {
  description = "EventBridge Scheduler expression, evaluated in Europe/London."
  type        = string
  default     = "cron(0 6 * * ? *)"
}

variable "schedule_enabled" {
  description = "Whether the daily schedule starts the pipeline."
  type        = bool
  default     = true
}

variable "alert_email" {
  description = "Address that receives failure notifications. Empty creates the topic with no subscriber. AWS emails a confirmation link that must be clicked once."
  type        = string
  default     = ""
}
