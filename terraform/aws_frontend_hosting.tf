# Frontend hosting is currently managed outside this Terraform module.
#
# The frontend environment values are exposed from outputs.tf via
# frontend_env_local_example.

locals {
  frontend_origin = var.frontend_local_origin
}
