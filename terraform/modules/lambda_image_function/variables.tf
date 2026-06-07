variable "function_name" {
  description = "Lambda function name."
  type        = string
}

variable "role_arn" {
  description = "IAM role ARN used by this Lambda."
  type        = string
}

variable "image_uri" {
  description = "Lambda container image URI."
  type        = string
}

variable "timeout" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 300
}

variable "memory_size" {
  description = "Lambda memory size in MB."
  type        = number
  default     = 1024
}

variable "environment_variables" {
  description = "Lambda environment variables."
  type        = map(string)
  default     = {}
}
