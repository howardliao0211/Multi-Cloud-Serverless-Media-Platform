locals {
  name_prefix = "${var.app_name}-${var.environment}"

  cognito_issuer = "https://cognito-idp.${var.aws_region}.amazonaws.com/${var.existing_cognito_user_pool_id}"

  common_tags = {
    Project     = "AussieEcoLens"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
