# Main Terraform entrypoint.
#
# Resource definitions are split by concern:
# - aws_existing.tf
# - aws_cognito.tf
# - aws_api_gateway.tf
# - aws_s3.tf
# - aws_dynamodb.tf
# - aws_lambda_iam.tf
# - aws_lambda_functions.tf
# - aws_frontend_hosting.tf
# - aws_dns.tf
# - gcp_iam.tf
#
# The first phase intentionally uses data sources only, so Terraform can read
# the current deployed AWS resources without modifying them.
