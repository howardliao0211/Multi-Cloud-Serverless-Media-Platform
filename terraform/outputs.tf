output "lambda_role_arns" {
  description = "IAM role ARN for each Lambda function."

  value = {
    for function_name, role_module in module.lambda_roles :
    function_name => role_module.role_arn
  }
}

output "lambda_role_names" {
  description = "IAM role name for each Lambda function."

  value = {
    for function_name, role_module in module.lambda_roles :
    function_name => role_module.role_name
  }
}

output "policy_arns" {
  description = "Reusable IAM policy ARNs."
  value       = module.iam_policies.policy_arns
}

output "lambda_function_arns" {
  description = "Lambda function ARNs managed by Terraform."

  value = {
    for function_name, lambda_module in module.lambda_functions :
    function_name => lambda_module.function_arn
  }
}
