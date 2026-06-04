# Existing API Gateway is looked up in aws_existing.tf:
# data "aws_apigatewayv2_api" "main" { ... }
#
# This project currently treats API Gateway as an existing deployed resource.
# Do not recreate it here unless the existing API, routes, integrations,
# authorizers, and stages have first been imported or fully modelled.

locals {
  api_gateway_endpoint = data.aws_apigatewayv2_api.main.api_endpoint
}
