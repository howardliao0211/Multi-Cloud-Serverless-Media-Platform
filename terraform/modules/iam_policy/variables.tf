variable "project_name" {
  description = "Project prefix."
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket name."
  type        = string
}

variable "media_table_name" {
  description = "DynamoDB media table name."
  type        = string
}

variable "subscription_table_name" {
  description = "DynamoDB subscription table name."
  type        = string
}

variable "sns_topic_name" {
  description = "SNS topic name."
  type        = string
}

variable "query_file_function_name" {
  description = "Name of the query_file Lambda function."
  type        = string
}

variable "lambda_invoke_function_names" {
  description = "Lambda function names that other project Lambdas may invoke."
  type        = list(string)
  default     = []
}
