resource "aws_secretsmanager_secret" "gcp_ml_hmac" {
  name        = "${local.name_prefix}/gcp-ml-hmac"
  description = "Shared HMAC secret used by AWS Lambda to call the GCP ML processor."
}

resource "aws_secretsmanager_secret_version" "gcp_ml_hmac" {
  secret_id     = aws_secretsmanager_secret.gcp_ml_hmac.id
  secret_string = var.internal_hmac_secret
}
