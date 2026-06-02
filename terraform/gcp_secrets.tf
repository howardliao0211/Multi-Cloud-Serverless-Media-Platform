resource "google_secret_manager_secret" "gcp_ml_hmac" {
  project   = var.gcp_project_id
  secret_id = "${local.name_prefix}-gcp-ml-hmac"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "gcp_ml_hmac" {
  secret      = google_secret_manager_secret.gcp_ml_hmac.id
  secret_data = var.internal_hmac_secret
}

resource "google_secret_manager_secret_iam_member" "ml_processor_hmac_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.gcp_ml_hmac.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.ml_processor.member
}
