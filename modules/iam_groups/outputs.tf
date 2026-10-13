output "bootstrap_group_name" {
  description = "Temporary group for running the bootstrap (and local dev applies)."
  value       = aws_iam_group.bootstrap.name
}

output "operator_group_name" {
  description = "Standing group for day-to-day operation."
  value       = aws_iam_group.operator.name
}
