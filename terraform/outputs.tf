output "environment" {
  value = var.environment
}

output "aws_region" {
  value = var.aws_region
}

output "gcp_project_id" {
  value = var.gcp_project_id
}

output "gcp_region" {
  value = var.gcp_region
}

output "current_api_endpoint" {
  value = data.aws_apigatewayv2_api.main.api_endpoint
}

output "current_media_bucket_name" {
  value = data.aws_s3_bucket.media.bucket
}

output "current_media_table_name" {
  value = data.aws_dynamodb_table.media.name
}

output "current_cognito_user_pool_id" {
  value = data.aws_cognito_user_pool.main.id
}

output "current_cognito_user_pool_client_id" {
  value = var.existing_cognito_user_pool_client_id
}

output "current_cognito_issuer" {
  value = local.cognito_issuer
}

output "frontend_env_local_example" {
  value = <<EOT
VITE_COGNITO_USER_POOL_ID="${data.aws_cognito_user_pool.main.id}"
VITE_COGNITO_USER_POOL_CLIENT_ID="${var.existing_cognito_user_pool_client_id}"
VITE_API_URL="${data.aws_apigatewayv2_api.main.api_endpoint}"
EOT
}

output "gcp_artifact_registry_repository" {
  value = google_artifact_registry_repository.containers.name
}

output "gcp_ml_processor_service_name" {
  value = google_cloud_run_v2_service.ml_processor.name
}

output "gcp_ml_processor_service_location" {
  value = google_cloud_run_v2_service.ml_processor.location
}

output "gcp_ml_processor_service_url" {
  value = google_cloud_run_v2_service.ml_processor.uri
}
