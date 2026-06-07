data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    sid    = "LambdaAssumeRole"
    effect = "Allow"

    principals {
      type = "Service"

      identifiers = [
        "lambda.amazonaws.com"
      ]
    }

    actions = [
      "sts:AssumeRole"
    ]
  }
}

resource "aws_iam_role" "this" {
  name = "${var.project_name}-${var.function_name}-role"

  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Project  = var.project_name
    Function = var.function_name
  }
}

resource "aws_iam_role_policy_attachment" "basic_execution" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
