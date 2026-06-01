variable "app_name" {
  description = "Application name prefix."
  type        = string
  default     = "aussie-eco-len"
}

variable "environment" {
  description = "Deployment environment name, for example us-demo or aus-demo."
  type        = string
  default     = "us-demo"
}

variable "aws_region" {
  description = "Primary AWS region."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Local AWS CLI profile used by Terraform."
  type        = string
  default     = "AussieEcoLense"
}

variable "gcp_project_id" {
  description = "GCP project ID for Cloud Run and Firestore."
  type        = string
  default     = "hazel-sphinx-490908-u6"
}

variable "gcp_region" {
  description = "GCP region for Cloud Run."
  type        = string
  default     = "us-east4"
}


variable "existing_api_id" {
  description = "Currently deployed API Gateway HTTP API ID."
  type        = string
  default     = "1jpi28kbj7"
}

variable "existing_media_bucket_name" {
  description = "Currently deployed S3 media bucket name."
  type        = string
  default     = "aussie-eco-len-bucket-12345"
}

variable "existing_media_table_name" {
  description = "Currently deployed DynamoDB media table name."
  type        = string
  default     = "aussie-eco-len-media"
}

variable "existing_cognito_user_pool_id" {
  description = "Currently deployed Cognito user pool ID."
  type        = string
  default     = "us-east-1_JefGiQ7lB"
}

variable "existing_cognito_user_pool_client_id" {
  description = "Currently deployed Cognito app client ID."
  type        = string
  default     = "7umv70h1q682h6pogi6hhc1lpc"
}

variable "frontend_local_origin" {
  description = "Local frontend origin for CORS."
  type        = string
  default     = "http://localhost:5173"
}

variable "domain_name" {
  description = "Root domain name for Route 53. Leave empty until DNS is ready."
  type        = string
  default     = ""
}

variable "gcp_artifact_registry_repository_id" {
  description = "Artifact Registry repository ID for GCP container images."
  type        = string
  default     = "aussie-ecolens"
}

variable "gcp_ml_processor_image" {
  description = "Container image URI for the GCP Cloud Run ML processor."
  type        = string
  default     = ""
}

variable "gcp_ml_processor_allow_public" {
  description = "Whether to allow unauthenticated invocation of the ML processor. HMAC still protects the endpoint."
  type        = bool
  default     = true
}

variable "internal_hmac_secret" {
  description = "Shared HMAC secret used by AWS Lambda to call GCP Cloud Run securely."
  type        = string
  sensitive   = true
}
