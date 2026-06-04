# Existing Lambda execution role is currently referenced by name where needed.
#
# Example existing role:
# - aussie-eco-len-lambda-role
#
# New IAM statements that Terraform owns should be kept close to the resource
# that needs them unless this file becomes the central IAM module.
