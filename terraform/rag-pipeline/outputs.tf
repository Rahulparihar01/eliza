output "vpc_id" {
  description = "VPC ID for the RAG pipeline"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "mwaa_webserver_url" {
  description = "MWAA Airflow webserver URL"
  value       = aws_mwaa_environment.main.webserver_url
}

output "mwaa_execution_role_arn" {
  description = "MWAA execution role ARN (grant to additional pipelines if needed)"
  value       = aws_iam_role.mwaa_execution.arn
}

output "mwaa_ui_access_policy_arn" {
  description = "IAM policy ARN for Airflow UI access. Attach to the IAM user or role used to open the console (e.g. SSO role) to fix 'Open Airflow UI' / SSO hanging or 403."
  value       = aws_iam_policy.mwaa_ui_access.arn
}

output "s3_raw_bucket" {
  description = "S3 bucket for raw ingested documents"
  value       = aws_s3_bucket.raw_documents.bucket
}

output "s3_processed_bucket" {
  description = "S3 bucket for processed/chunked documents"
  value       = aws_s3_bucket.processed_documents.bucket
}

output "s3_dags_bucket" {
  description = "S3 bucket for Airflow DAG files"
  value       = aws_s3_bucket.airflow_dags.bucket
}

output "opensearch_endpoint" {
  description = "OpenSearch Serverless collection endpoint"
  value       = aws_opensearchserverless_collection.rag_vectors.collection_endpoint
}

output "opensearch_collection_arn" {
  description = "OpenSearch Serverless collection ARN"
  value       = aws_opensearchserverless_collection.rag_vectors.arn
}

output "api_gateway_url" {
  description = "MCP API Gateway endpoint"
  value       = aws_apigatewayv2_api.mcp.api_endpoint
}

output "mcp_nlb_target_group_arn" {
  description = "Target group ARN for MCP server — attach ECS service or register IP targets (port 8888)"
  value       = aws_lb_target_group.mcp.arn
}
