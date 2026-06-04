# Existing DynamoDB media table is looked up in aws_existing.tf:
# data "aws_dynamodb_table" "media" { ... }
#
# The table is currently treated as an existing deployed resource to avoid
# replacing live media metadata.

locals {
  media_table_name = data.aws_dynamodb_table.media.name
}
