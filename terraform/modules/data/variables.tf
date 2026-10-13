variable "name_prefix" {
  description = "Prefix for bucket names, e.g. skillsradar-dev."
  type        = string
}

variable "force_destroy" {
  description = "Allow terraform destroy to delete non-empty buckets (dev only)."
  type        = bool
  default     = false
}
