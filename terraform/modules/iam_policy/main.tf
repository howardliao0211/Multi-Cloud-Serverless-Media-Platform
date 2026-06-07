data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.region

  bucket_arn = "arn:aws:s3:::${var.bucket_name}"

  media_table_arn = "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${var.media_table_name}"

  media_table_stream_arn = "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${var.media_table_name}/stream/*"

  subscription_table_arn = "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${var.subscription_table_name}"

  sns_topic_arn = "arn:aws:sns:${local.region}:${local.account_id}:${var.sns_topic_name}"

  query_file_function_arn = "arn:aws:lambda:${local.region}:${local.account_id}:function:${var.query_file_function_name}"

  lambda_invoke_function_arns = distinct(concat(
    [
      local.query_file_function_arn
    ],
    [
      for function_name in var.lambda_invoke_function_names :
      "arn:aws:lambda:${local.region}:${local.account_id}:function:${function_name}"
    ]
  ))

  s3_read_object_arns = [
    "${local.bucket_arn}/images/*",
    "${local.bucket_arn}/videos/*",
    "${local.bucket_arn}/thumbnails/*",
    "${local.bucket_arn}/models/*",
    "${local.bucket_arn}/query_uploads/*"
  ]

  s3_write_object_arns = [
    "${local.bucket_arn}/images/*",
    "${local.bucket_arn}/videos/*",
    "${local.bucket_arn}/thumbnails/*",
    "${local.bucket_arn}/query_uploads/*"
  ]

  s3_upload_object_arns = [
    "${local.bucket_arn}/images/*",
    "${local.bucket_arn}/videos/*"
  ]

  s3_thumbnail_object_arns = [
    "${local.bucket_arn}/thumbnails/*"
  ]

  s3_query_upload_object_arns = [
    "${local.bucket_arn}/query_uploads/*"
  ]

  s3_allowed_prefixes = [
    "images/*",
    "videos/*",
    "thumbnails/*",
    "models/*",
    "query_uploads/*"
  ]
}

data "aws_iam_policy_document" "s3_media_rw" {
  statement {
    sid    = "S3MediaBucketAccess"
    effect = "Allow"

    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads"
    ]

    resources = [
      local.bucket_arn
    ]
  }

  statement {
    sid    = "S3MediaObjectReadWrite"
    effect = "Allow"

    actions = [
      "s3:AbortMultipartUpload",
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:GetObjectAttributes",
      "s3:GetObjectTagging",
      "s3:ListMultipartUploadParts",
      "s3:PutObject",
      "s3:PutObjectTagging"
    ]

    resources = [
      "${local.bucket_arn}/*"
    ]
  }
}

resource "aws_iam_policy" "s3_media_rw" {
  name        = "${var.project_name}-s3-media-rw"
  description = "Allow Lambda functions to read and write project media objects in S3."
  policy      = data.aws_iam_policy_document.s3_media_rw.json
}

data "aws_iam_policy_document" "s3_read_media" {
  statement {
    sid    = "S3ReadMediaObjects"
    effect = "Allow"

    actions = [
      "s3:GetObject"
    ]

    resources = local.s3_read_object_arns
  }

  statement {
    sid    = "S3ListMediaPrefixes"
    effect = "Allow"

    actions = [
      "s3:ListBucket"
    ]

    resources = [
      local.bucket_arn
    ]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = local.s3_allowed_prefixes
    }
  }
}

resource "aws_iam_policy" "s3_read_media" {
  name        = "${var.project_name}-s3-read-media"
  description = "Allow Lambda functions to read media objects from S3."
  policy      = data.aws_iam_policy_document.s3_read_media.json
}

data "aws_iam_policy_document" "s3_write_media" {
  statement {
    sid    = "S3WriteMediaObjects"
    effect = "Allow"

    actions = [
      "s3:PutObject",
      "s3:DeleteObject"
    ]

    resources = local.s3_write_object_arns
  }
}

resource "aws_iam_policy" "s3_write_media" {
  name        = "${var.project_name}-s3-write-media"
  description = "Allow Lambda functions to write media objects to S3."
  policy      = data.aws_iam_policy_document.s3_write_media.json
}

data "aws_iam_policy_document" "s3_put_upload_media" {
  statement {
    sid    = "S3PutUploadMediaObjects"
    effect = "Allow"

    actions = [
      "s3:PutObject"
    ]

    resources = local.s3_upload_object_arns
  }
}

resource "aws_iam_policy" "s3_put_upload_media" {
  name        = "${var.project_name}-s3-put-upload-media"
  description = "Allow Lambda functions to create presigned uploads for image and video media."
  policy      = data.aws_iam_policy_document.s3_put_upload_media.json
}

data "aws_iam_policy_document" "s3_put_query_uploads" {
  statement {
    sid    = "S3PutQueryUploadObjects"
    effect = "Allow"

    actions = [
      "s3:PutObject"
    ]

    resources = local.s3_query_upload_object_arns
  }
}

resource "aws_iam_policy" "s3_put_query_uploads" {
  name        = "${var.project_name}-s3-put-query-uploads"
  description = "Allow Lambda functions to create presigned uploads for query files."
  policy      = data.aws_iam_policy_document.s3_put_query_uploads.json
}

data "aws_iam_policy_document" "s3_put_thumbnails" {
  statement {
    sid    = "S3PutThumbnailObjects"
    effect = "Allow"

    actions = [
      "s3:PutObject"
    ]

    resources = local.s3_thumbnail_object_arns
  }
}

resource "aws_iam_policy" "s3_put_thumbnails" {
  name        = "${var.project_name}-s3-put-thumbnails"
  description = "Allow Lambda functions to write generated thumbnails."
  policy      = data.aws_iam_policy_document.s3_put_thumbnails.json
}

data "aws_iam_policy_document" "s3_delete_media" {
  statement {
    sid    = "S3DeleteMediaObjects"
    effect = "Allow"

    actions = [
      "s3:DeleteObject"
    ]

    resources = concat(
      local.s3_upload_object_arns,
      local.s3_thumbnail_object_arns
    )
  }
}

resource "aws_iam_policy" "s3_delete_media" {
  name        = "${var.project_name}-s3-delete-media"
  description = "Allow Lambda functions to delete stored media and thumbnails."
  policy      = data.aws_iam_policy_document.s3_delete_media.json
}

data "aws_iam_policy_document" "s3_delete_query_uploads" {
  statement {
    sid    = "S3DeleteQueryUploadObjects"
    effect = "Allow"

    actions = [
      "s3:DeleteObject"
    ]

    resources = local.s3_query_upload_object_arns
  }
}

resource "aws_iam_policy" "s3_delete_query_uploads" {
  name        = "${var.project_name}-s3-delete-query-uploads"
  description = "Allow Lambda functions to clean up temporary query uploads."
  policy      = data.aws_iam_policy_document.s3_delete_query_uploads.json
}

data "aws_iam_policy_document" "dynamodb_media_rw" {
  statement {
    sid    = "DynamoDBMediaReadWrite"
    effect = "Allow"

    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan"
    ]

    resources = [
      local.media_table_arn,
      "${local.media_table_arn}/index/*"
    ]
  }
}

resource "aws_iam_policy" "dynamodb_media_rw" {
  name        = "${var.project_name}-dynamodb-media-rw"
  description = "Allow Lambda functions to read and write the media table."
  policy      = data.aws_iam_policy_document.dynamodb_media_rw.json
}

data "aws_iam_policy_document" "dynamodb_media_read" {
  statement {
    sid    = "DynamoDBMediaRead"
    effect = "Allow"

    actions = [
      "dynamodb:GetItem",
      "dynamodb:Query",
      "dynamodb:Scan"
    ]

    resources = [
      local.media_table_arn,
      "${local.media_table_arn}/index/*"
    ]
  }
}

resource "aws_iam_policy" "dynamodb_media_read" {
  name        = "${var.project_name}-dynamodb-media-read"
  description = "Allow Lambda functions to read the media table."
  policy      = data.aws_iam_policy_document.dynamodb_media_read.json
}

data "aws_iam_policy_document" "dynamodb_media_put" {
  statement {
    sid    = "DynamoDBMediaPut"
    effect = "Allow"

    actions = [
      "dynamodb:PutItem"
    ]

    resources = [
      local.media_table_arn
    ]
  }
}

resource "aws_iam_policy" "dynamodb_media_put" {
  name        = "${var.project_name}-dynamodb-media-put"
  description = "Allow Lambda functions to insert media table records."
  policy      = data.aws_iam_policy_document.dynamodb_media_put.json
}

data "aws_iam_policy_document" "dynamodb_media_update" {
  statement {
    sid    = "DynamoDBMediaUpdate"
    effect = "Allow"

    actions = [
      "dynamodb:UpdateItem"
    ]

    resources = [
      local.media_table_arn
    ]
  }
}

resource "aws_iam_policy" "dynamodb_media_update" {
  name        = "${var.project_name}-dynamodb-media-update"
  description = "Allow Lambda functions to update media table records."
  policy      = data.aws_iam_policy_document.dynamodb_media_update.json
}

data "aws_iam_policy_document" "dynamodb_media_delete" {
  statement {
    sid    = "DynamoDBMediaDelete"
    effect = "Allow"

    actions = [
      "dynamodb:DeleteItem"
    ]

    resources = [
      local.media_table_arn
    ]
  }
}

resource "aws_iam_policy" "dynamodb_media_delete" {
  name        = "${var.project_name}-dynamodb-media-delete"
  description = "Allow Lambda functions to delete media table records."
  policy      = data.aws_iam_policy_document.dynamodb_media_delete.json
}

data "aws_iam_policy_document" "dynamodb_subscription_rw" {
  statement {
    sid    = "DynamoDBSubscriptionReadWrite"
    effect = "Allow"

    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan"
    ]

    resources = [
      local.subscription_table_arn,
      "${local.subscription_table_arn}/index/*"
    ]
  }
}

resource "aws_iam_policy" "dynamodb_subscription_rw" {
  name        = "${var.project_name}-dynamodb-subscription-rw"
  description = "Allow Lambda functions to read and write the subscription table."
  policy      = data.aws_iam_policy_document.dynamodb_subscription_rw.json
}

data "aws_iam_policy_document" "dynamodb_stream_read" {
  statement {
    sid    = "DynamoDBStreamRead"
    effect = "Allow"

    actions = [
      "dynamodb:DescribeStream",
      "dynamodb:GetRecords",
      "dynamodb:GetShardIterator",
      "dynamodb:ListStreams"
    ]

    resources = [
      local.media_table_stream_arn
    ]
  }
}

resource "aws_iam_policy" "dynamodb_stream_read" {
  name        = "${var.project_name}-dynamodb-stream-read"
  description = "Allow Lambda functions to read DynamoDB streams."
  policy      = data.aws_iam_policy_document.dynamodb_stream_read.json
}

data "aws_iam_policy_document" "sns_publish" {
  statement {
    sid    = "SNSPublish"
    effect = "Allow"

    actions = [
      "sns:Publish"
    ]

    resources = [
      local.sns_topic_arn
    ]
  }
}

resource "aws_iam_policy" "sns_publish" {
  name        = "${var.project_name}-sns-publish"
  description = "Allow Lambda functions to publish to SNS."
  policy      = data.aws_iam_policy_document.sns_publish.json
}

data "aws_iam_policy_document" "sns_subscription_manage" {
  statement {
    sid    = "SNSSubscriptionManagement"
    effect = "Allow"

    actions = [
      "sns:GetTopicAttributes",
      "sns:Subscribe",
      "sns:SetSubscriptionAttributes",
      "sns:ListSubscriptionsByTopic",
      "sns:Unsubscribe",
      "sns:GetSubscriptionAttributes",
      "sns:Publish"
    ]

    resources = [
      local.sns_topic_arn
    ]
  }
}

resource "aws_iam_policy" "sns_subscription_manage" {
  name        = "${var.project_name}-sns-subscription-manage"
  description = "Allow Lambda functions to manage SNS subscriptions."
  policy      = data.aws_iam_policy_document.sns_subscription_manage.json
}

data "aws_iam_policy_document" "sns_subscription_read" {
  statement {
    sid    = "SNSSubscriptionRead"
    effect = "Allow"

    actions = [
      "sns:ListSubscriptionsByTopic",
      "sns:GetSubscriptionAttributes"
    ]

    resources = [
      local.sns_topic_arn
    ]
  }
}

resource "aws_iam_policy" "sns_subscription_read" {
  name        = "${var.project_name}-sns-subscription-read"
  description = "Allow Lambda functions to read SNS subscription status."
  policy      = data.aws_iam_policy_document.sns_subscription_read.json
}

data "aws_iam_policy_document" "sns_subscription_subscribe" {
  statement {
    sid    = "SNSSubscriptionSubscribe"
    effect = "Allow"

    actions = [
      "sns:ListSubscriptionsByTopic",
      "sns:Subscribe",
      "sns:SetSubscriptionAttributes"
    ]

    resources = [
      local.sns_topic_arn
    ]
  }
}

resource "aws_iam_policy" "sns_subscription_subscribe" {
  name        = "${var.project_name}-sns-subscription-subscribe"
  description = "Allow Lambda functions to create or update SNS email subscriptions."
  policy      = data.aws_iam_policy_document.sns_subscription_subscribe.json
}

data "aws_iam_policy_document" "sns_subscription_unsubscribe" {
  statement {
    sid    = "SNSSubscriptionUnsubscribe"
    effect = "Allow"

    actions = [
      "sns:ListSubscriptionsByTopic",
      "sns:Unsubscribe"
    ]

    resources = [
      local.sns_topic_arn
    ]
  }
}

resource "aws_iam_policy" "sns_subscription_unsubscribe" {
  name        = "${var.project_name}-sns-subscription-unsubscribe"
  description = "Allow Lambda functions to remove SNS email subscriptions."
  policy      = data.aws_iam_policy_document.sns_subscription_unsubscribe.json
}

data "aws_iam_policy_document" "invoke_query_file" {
  statement {
    sid    = "InvokeQueryFile"
    effect = "Allow"

    actions = [
      "lambda:InvokeFunction"
    ]

    resources = [
      local.query_file_function_arn
    ]
  }
}

resource "aws_iam_policy" "invoke_query_file" {
  name        = "${var.project_name}-invoke-query-file"
  description = "Allow Lambda functions to invoke query_file."
  policy      = data.aws_iam_policy_document.invoke_query_file.json
}

data "aws_iam_policy_document" "lambda_invoke" {
  statement {
    sid    = "InvokeProjectWorkers"
    effect = "Allow"

    actions = [
      "lambda:InvokeFunction"
    ]

    resources = local.lambda_invoke_function_arns
  }
}

resource "aws_iam_policy" "lambda_invoke" {
  name        = "${var.project_name}-lambda-invoke"
  description = "Allow Lambda functions to invoke project worker functions."
  policy      = data.aws_iam_policy_document.lambda_invoke.json
}

data "aws_iam_policy_document" "secretsmanager_read" {
  statement {
    sid    = "ReadRuntimeSecrets"
    effect = "Allow"

    actions = [
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetSecretValue"
    ]

    resources = [
      "*"
    ]
  }
}

resource "aws_iam_policy" "secretsmanager_read" {
  name        = "${var.project_name}-secretsmanager-read"
  description = "Allow Lambda functions to read runtime secrets."
  policy      = data.aws_iam_policy_document.secretsmanager_read.json
}
