output "bootstrap_group_name" {
  value = aws_iam_group.bootstrap.name
}

output "operator_group_name" {
  value = aws_iam_group.operator.name
}

output "bootstrap_policy_arn" {
  value = aws_iam_policy.bootstrap.arn
}

output "operator_policy_arn" {
  value = aws_iam_policy.operator.arn
}
