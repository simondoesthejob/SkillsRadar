output "database_name" {
  description = "Glue database holding the tables."
  value       = aws_glue_catalog_database.this.name
}

output "table_name" {
  description = "Glue table over the raw postings."
  value       = aws_glue_catalog_table.raw_postings.name
}

output "workgroup_name" {
  description = "Athena workgroup to run queries in."
  value       = aws_athena_workgroup.this.name
}
