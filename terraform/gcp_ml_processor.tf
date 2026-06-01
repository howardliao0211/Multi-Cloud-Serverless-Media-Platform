resource "google_service_account" "ml_processor" {
  project      = var.gcp_project_id
  account_id   = "${local.name_prefix}-ml"
  display_name = "Aussie EcoLens ML processor service account (${var.environment})"
}

resource "google_cloud_run_v2_service" "ml_processor" {
  project  = var.gcp_project_id
  name     = "${local.name_prefix}-ml-processor"
  location = var.gcp_region

  deletion_protection = false

  template {
    service_account = google_service_account.ml_processor.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.gcp_ml_processor_image

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "INTERNAL_HMAC_SECRET"
        value = var.internal_hmac_secret
      }

      env {
        name  = "MAX_TIME_SKEW_SECONDS"
        value = "300"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "ml_processor_public_invoker" {
  count = var.gcp_ml_processor_allow_public ? 1 : 0

  project  = var.gcp_project_id
  location = google_cloud_run_v2_service.ml_processor.location
  name     = google_cloud_run_v2_service.ml_processor.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
