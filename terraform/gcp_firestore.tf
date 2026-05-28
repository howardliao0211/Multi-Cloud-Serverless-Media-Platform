resource "google_firestore_database" "metadata_replica" {
  project     = var.gcp_project_id
  name        = "(default)"
  location_id = var.gcp_firestore_location
  type        = "FIRESTORE_NATIVE"

  # For assignment/demo environments, allow Terraform destroy if needed.
  # For a real production environment, change this to DELETE_PROTECTION_ENABLED.
  delete_protection_state = "DELETE_PROTECTION_DISABLED"
  deletion_policy         = "DELETE"
}
