resource "aws_lambda_function" "this" {
  function_name = var.function_name
  role          = var.role_arn

  package_type = "Image"
  image_uri    = var.image_uri

  timeout     = var.timeout
  memory_size = var.memory_size

  environment {
    variables = var.environment_variables
  }

  lifecycle {
    ignore_changes = [
      environment,
      image_uri
    ]
  }
}
