resource "google_artifact_registry_repository" "containers" {
  project       = var.gcp_project_id
  location      = var.gcp_region
  repository_id = var.gcp_artifact_registry_repository_id
  description   = "Container images for Aussie EcoLens ${var.environment}"
  format        = "DOCKER"
}
