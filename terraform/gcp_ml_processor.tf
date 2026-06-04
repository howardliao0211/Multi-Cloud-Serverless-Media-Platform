resource "google_service_account" "ml_processor" {
  project      = var.gcp_project_id
  account_id   = "${local.name_prefix}-ml"
  display_name = "Aussie EcoLens ML processor service account (${var.environment})"
}

resource "google_cloud_run_v2_service" "ml_processor" {
  name                = "aussie-eco-len-${var.environment}-ml-processor"
  location            = var.gcp_region
  project             = var.gcp_project_id
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  lifecycle {
    ignore_changes = [
      template,
      client,
      client_version,
    ]
  }

  template {
    gpu_zonal_redundancy_disabled = true

    annotations = {
      "autoscaling.knative.dev/minScale"                 = "0"
      "autoscaling.knative.dev/maxScale"                 = "2"
      "run.googleapis.com/cpu-throttling"                = "false"
      "run.googleapis.com/execution-environment"         = "gen2"
      "run.googleapis.com/gpu-zonal-redundancy-disabled" = "true"
    }

    node_selector {
      accelerator = "nvidia-l4"
    }

    max_instance_request_concurrency = 2

    containers {
      image = var.gcp_ml_processor_image

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "GCP_CLASSIFIER_MODEL_URL"
        value = var.gcp_classifier_model_url
      }

      env {
        name  = "GCP_DETECTOR_MODEL_URL"
        value = var.gcp_detector_model_url
      }

      env {
        name  = "GCP_MODEL_VERSION"
        value = var.gcp_model_version
      }

      env {
        name  = "GCP_MODEL_CACHE_DIR"
        value = var.gcp_model_cache_dir
      }

      env {
        name = "INTERNAL_HMAC_SECRET"

        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gcp_ml_hmac.id
            version = "latest"
          }
        }
      }

      env {
        name  = "MAX_TIME_SKEW_SECONDS"
        value = "300"
      }

      resources {
        limits = {
          cpu              = var.gcp_ml_processor_cpu
          memory           = var.gcp_ml_processor_memory
          "nvidia.com/gpu" = var.gcp_ml_processor_gpu_count
        }

        cpu_idle = false
      }

      startup_probe {
        timeout_seconds   = 240
        period_seconds    = 240
        failure_threshold = 1

        tcp_socket {
          port = 8080
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
