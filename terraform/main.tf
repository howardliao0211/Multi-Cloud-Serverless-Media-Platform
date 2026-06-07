terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "lambda_roles" {
  source = "./modules/lambda_iam_role"

  for_each = local.lambda_names

  project_name  = var.project_name
  function_name = each.key
}

module "iam_policies" {
  source = "./modules/iam_policy"

  project_name             = var.project_name
  bucket_name              = var.bucket_name
  media_table_name         = var.media_table_name
  subscription_table_name  = var.subscription_table_name
  sns_topic_name           = var.sns_topic_name
  query_file_function_name = "query_file"
  lambda_invoke_function_names = [
    "query_file",
    "process_ml_result"
  ]
}

locals {
  lambda_policy_attachments = {
    change_visibility = [
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    create_query_file_job = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw,
      module.iam_policies.policy_arns.lambda_invoke
    ]

    delete_file = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    edit_tags = [
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    get_signed_url = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    get_private_media = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    get_public_media = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    get_query_file_job = [
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    get_query_upload_url = [
      module.iam_policies.policy_arns.s3_media_rw
    ]

    get_subscription = [
      module.iam_policies.policy_arns.sns_topic_manage
    ]

    get_upload_status = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    media_ingest = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw,
      module.iam_policies.policy_arns.lambda_invoke,
      module.iam_policies.policy_arns.secretsmanager_read
    ]

    process_ml_result = [
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    publish_tags = [
      module.iam_policies.policy_arns.dynamodb_stream_read,
      module.iam_policies.policy_arns.sns_topic_manage
    ]

    query_file = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    query_species = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    query_tags = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    query_thumbnail_url = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw
    ]

    tag_image = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw,
      module.iam_policies.policy_arns.sns_topic_manage,
      module.iam_policies.policy_arns.secretsmanager_read
    ]

    tag_video = [
      module.iam_policies.policy_arns.s3_media_rw,
      module.iam_policies.policy_arns.dynamodb_media_rw,
      module.iam_policies.policy_arns.sns_topic_manage
    ]

    subscribe_tags = [
      module.iam_policies.policy_arns.sns_topic_manage
    ]

    unsubscribe_tags = [
      module.iam_policies.policy_arns.sns_topic_manage
    ]
  }

  flattened_lambda_policy_attachments = flatten([
    for function_name, policy_arns in local.lambda_policy_attachments : [
      for index, policy_arn in policy_arns : {
        key           = "${function_name}-${index}"
        function_name = function_name
        policy_arn    = policy_arn
      }
    ]
  ])
}

resource "aws_iam_role_policy_attachment" "function_specific_policy" {
  for_each = {
    for attachment in local.flattened_lambda_policy_attachments :
    attachment.key => attachment
  }

  role       = module.lambda_roles[each.value.function_name].role_name
  policy_arn = each.value.policy_arn
}

module "lambda_functions" {
  source = "./modules/lambda_image_function"

  for_each = {
    for name, image_uri in var.lambda_image_uris :
    name => image_uri
    if image_uri != ""
  }

  function_name = each.key
  image_uri     = each.value
  role_arn      = module.lambda_roles[each.key].role_arn

  timeout     = lookup(var.lambda_timeouts, each.key, 300)
  memory_size = lookup(var.lambda_memory_sizes, each.key, 1024)

  environment_variables = {
    BUCKET_NAME             = var.bucket_name
    MEDIA_TABLE_NAME        = var.media_table_name
    SUBSCRIPTION_TABLE_NAME = var.subscription_table_name
    SNS_TOPIC_NAME          = var.sns_topic_name
  }

  depends_on = [
    aws_iam_role_policy_attachment.function_specific_policy
  ]
}
