data "aws_iam_role" "lambda_execution" {
  name = var.existing_lambda_role_name
}

data "aws_iam_policy_document" "lambda_runtime" {
  statement {
    sid = "WriteCloudWatchLogs"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/*",
    ]
  }

  statement {
    sid = "AccessMediaBucketObjects"

    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:HeadObject",
      "s3:PutObject",
    ]

    resources = [
      "${data.aws_s3_bucket.media.arn}/*",
    ]
  }

  statement {
    sid = "AccessMediaTable"

    actions = [
      "dynamodb:DeleteItem",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:UpdateItem",
    ]

    resources = [
      data.aws_dynamodb_table.media.arn,
      "${data.aws_dynamodb_table.media.arn}/index/*",
    ]
  }

  statement {
    sid = "InvokeQueryFileWorker"

    actions = [
      "lambda:InvokeFunction",
    ]

    resources = [
      "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:query_file",
    ]
  }

  statement {
    sid = "ReadGcpMlHmacSecret"

    actions = [
      "secretsmanager:GetSecretValue",
    ]

    resources = [
      aws_secretsmanager_secret.gcp_ml_hmac.arn,
    ]
  }
}

resource "aws_iam_role_policy" "lambda_runtime" {
  name   = "${local.name_prefix}-lambda-runtime"
  role   = data.aws_iam_role.lambda_execution.name
  policy = data.aws_iam_policy_document.lambda_runtime.json
}
