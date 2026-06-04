# Existing Cognito user pool is looked up in aws_existing.tf:
# data "aws_cognito_user_pool" "main" { ... }
#
# The user pool and app client are currently managed outside this Terraform
# module. Keep this file as a safe reference point until Cognito is imported
# or recreated intentionally.

locals {
  cognito_user_pool_id        = data.aws_cognito_user_pool.main.id
  cognito_user_pool_client_id = var.existing_cognito_user_pool_client_id
}
