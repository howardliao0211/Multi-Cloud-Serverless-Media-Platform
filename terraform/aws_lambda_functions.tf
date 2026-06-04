# Lambda functions are currently deployed by the existing backend deployment
# scripts and referenced by name from Terraform-managed permissions.
#
# This file is reserved for future Lambda ownership/import if needed.
#
# Current functions referenced by Terraform/scripts include:
# - tag_image
# - tag_video
# - query_file
# - change_visibility
