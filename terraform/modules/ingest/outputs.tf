output "function_name" {
  value = aws_lambda_function.ingest.function_name
}

output "adzuna_secret_arn" {
  value = aws_secretsmanager_secret.adzuna.arn
}

output "reed_secret_arn" {
  value = aws_secretsmanager_secret.reed.arn
}

output "dlq_url" {
  value = aws_sqs_queue.dlq.url
}

output "function_arn" {
  value = aws_lambda_function.ingest.arn
}
