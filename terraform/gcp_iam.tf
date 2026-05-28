resource "google_service_account" "cloud_run_query" {
  project      = var.gcp_project_id
  account_id   = "${local.name_prefix}-query"
  display_name = "Aussie EcoLens Cloud Run query service account (${var.environment})"
}

resource "google_project_iam_member" "cloud_run_query_firestore_user" {
  project = var.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloud_run_query.email}"
}
