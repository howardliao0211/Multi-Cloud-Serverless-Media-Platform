resource "google_iam_workload_identity_pool" "aws_lambda" {
  project                   = var.gcp_project_id
  workload_identity_pool_id = "${local.name_prefix}-aws"
  display_name              = "AWS Lambda federation (${var.environment})"
  description               = "Allows selected AWS Lambda role to authenticate to GCP without service account keys."
}

resource "google_iam_workload_identity_pool_provider" "aws_lambda" {
  project                            = var.gcp_project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.aws_lambda.workload_identity_pool_id
  workload_identity_pool_provider_id = "aws-lambda"
  display_name                       = "AWS Lambda provider"

  aws {
    account_id = data.aws_caller_identity.current.account_id
  }

  attribute_mapping = {
    "google.subject"        = "assertion.arn"
    "attribute.aws_role"    = "assertion.arn"
    "attribute.aws_account" = "assertion.account"
  }

  attribute_condition = "assertion.arn == 'arn:aws:sts::${data.aws_caller_identity.current.account_id}:assumed-role/aussie-eco-len-lambda-role/tag_image'"
}

resource "google_service_account" "aws_lambda_invoker" {
  project      = var.gcp_project_id
  account_id   = "ael-us-aws-invoker"
  display_name = "AWS Lambda Cloud Run invoker (${var.environment})"
}

resource "google_service_account_iam_member" "aws_lambda_can_impersonate_invoker" {
  service_account_id = google_service_account.aws_lambda_invoker.name
  role               = "roles/iam.workloadIdentityUser"

  member = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.aws_lambda.name}/attribute.aws_role/arn:aws:sts::${data.aws_caller_identity.current.account_id}:assumed-role/aussie-eco-len-lambda-role/tag_image"
}

resource "google_cloud_run_v2_service_iam_member" "ml_processor_aws_invoker" {
  project  = var.gcp_project_id
  location = google_cloud_run_v2_service.ml_processor.location
  name     = google_cloud_run_v2_service.ml_processor.name
  role     = "roles/run.invoker"
  member   = google_service_account.aws_lambda_invoker.member
}
