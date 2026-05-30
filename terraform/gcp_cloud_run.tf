resource "google_cloud_run_v2_service" "query" {
  project  = var.gcp_project_id
  name     = "${local.name_prefix}-query"
  location = var.gcp_region

  deletion_protection = false

  template {
    service_account = google_service_account.cloud_run_query.email

    containers {
      image = var.gcp_cloud_run_image

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "FIRESTORE_PROJECT_ID"
        value = var.gcp_project_id
      }

      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.metadata_replica.name
      }

      env {
        name  = "COGNITO_ISSUER"
        value = local.cognito_issuer
      }

      env {
        name  = "COGNITO_AUDIENCE"
        value = var.existing_cognito_user_pool_client_id
      }

      env {
        name  = "AWS_API_ENDPOINT"
        value = data.aws_apigatewayv2_api.main.api_endpoint
      }

      env {
        name  = "MEDIA_PUBLIC_BASE_URL"
        value = "https://${data.aws_s3_bucket.media.bucket}.s3.amazonaws.com"
      }
    }
  }

  depends_on = [
    google_project_iam_member.cloud_run_query_firestore_user
  ]
}

resource "google_cloud_run_v2_service_iam_member" "query_public_invoker" {
  count = var.gcp_cloud_run_allow_public ? 1 : 0

  project  = var.gcp_project_id
  location = google_cloud_run_v2_service.query.location
  name     = google_cloud_run_v2_service.query.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
