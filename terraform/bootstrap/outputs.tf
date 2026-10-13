output "state_bucket" {
  description = "Set as the TF_STATE_BUCKET repository variable in GitHub."
  value       = aws_s3_bucket.state.id
}

output "plan_role_arn" {
  description = "Set as the AWS_PLAN_ROLE_ARN repository variable in GitHub."
  value       = module.github_oidc.plan_role_arn
}

output "apply_role_arn" {
  description = "Set as the AWS_APPLY_ROLE_ARN variable on the 'dev' GitHub environment."
  value       = module.github_oidc.apply_role_arn
}
