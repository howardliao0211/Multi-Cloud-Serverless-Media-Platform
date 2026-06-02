resource "aws_secretsmanager_secret" "gcp_ml_hmac" {
  name        = "${local.name_prefix}/gcp-ml-hmac"
  description = "Shared HMAC secret used by AWS Lambda to call the GCP ML processor."
}

resource "aws_secretsmanager_secret_version" "gcp_ml_hmac" {
  secret_id     = aws_secretsmanager_secret.gcp_ml_hmac.id
  secret_string = var.internal_hmac_secret
}

resource "aws_iam_role_policy" "lambda_read_gcp_ml_hmac_secret" {
  name = "${local.name_prefix}-lambda-read-gcp-ml-hmac"
  role = "aussie-eco-len-lambda-role"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.gcp_ml_hmac.arn
      }
    ]
  })
}
