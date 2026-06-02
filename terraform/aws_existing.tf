data "aws_s3_bucket" "media" {
  bucket = var.existing_media_bucket_name
}

data "aws_dynamodb_table" "media" {
  name = var.existing_media_table_name
}

data "aws_cognito_user_pool" "main" {
  user_pool_id = var.existing_cognito_user_pool_id
}

data "aws_apigatewayv2_api" "main" {
  api_id = var.existing_api_id
}

data "aws_caller_identity" "current" {}
