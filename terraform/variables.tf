variable "aws_region" {
  description = "AWS region for the project."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project prefix."
  type        = string
  default     = "aussie-eco-len"
}

variable "bucket_name" {
  description = "S3 bucket name."
  type        = string
  default     = "aussie-eco-len-bucket-12345"
}

variable "media_table_name" {
  description = "DynamoDB media table name."
  type        = string
  default     = "aussie-eco-len-media"
}

variable "subscription_table_name" {
  description = "DynamoDB subscription table name."
  type        = string
  default     = "aussie-eco-len-subscriptions"
}

variable "sns_topic_name" {
  description = "SNS topic name."
  type        = string
  default     = "image-tag-notifications"
}

variable "lambda_image_uris" {
  description = "Container image URI for each Lambda."
  type        = map(string)

  default = {
    change_visibility     = "539913718279.dkr.ecr.us-east-1.amazonaws.com/change_visibility:latest"
    create_query_file_job = "539913718279.dkr.ecr.us-east-1.amazonaws.com/create_query_file_job:latest"
    delete_file           = "539913718279.dkr.ecr.us-east-1.amazonaws.com/delete_file:latest"
    edit_tags             = "539913718279.dkr.ecr.us-east-1.amazonaws.com/edit_tags:latest"
    get_private_media     = "539913718279.dkr.ecr.us-east-1.amazonaws.com/get_private_media:latest"
    get_public_media      = "539913718279.dkr.ecr.us-east-1.amazonaws.com/get_public_media:latest"
    get_query_file_job    = "539913718279.dkr.ecr.us-east-1.amazonaws.com/get_query_file_job:latest"
    get_query_upload_url  = "539913718279.dkr.ecr.us-east-1.amazonaws.com/get_query_upload_url:latest"
    get_signed_url        = "539913718279.dkr.ecr.us-east-1.amazonaws.com/get_signed_url:latest"
    get_subscription      = "539913718279.dkr.ecr.us-east-1.amazonaws.com/get_subscription:latest"
    get_upload_status     = "539913718279.dkr.ecr.us-east-1.amazonaws.com/get_upload_status:latest"
    media_ingest          = "539913718279.dkr.ecr.us-east-1.amazonaws.com/media_ingest:latest"
    process_ml_result     = "539913718279.dkr.ecr.us-east-1.amazonaws.com/process_ml_result:latest"
    publish_tags          = "539913718279.dkr.ecr.us-east-1.amazonaws.com/publish_tags:latest"
    query_file            = "539913718279.dkr.ecr.us-east-1.amazonaws.com/query_file:latest"
    query_species         = "539913718279.dkr.ecr.us-east-1.amazonaws.com/query_species:latest"
    query_tags            = "539913718279.dkr.ecr.us-east-1.amazonaws.com/query_tags:latest"
    query_thumbnail_url   = "539913718279.dkr.ecr.us-east-1.amazonaws.com/query_thumbnail_url:latest"
    tag_image             = "539913718279.dkr.ecr.us-east-1.amazonaws.com/tag_image:latest"
    tag_video             = "539913718279.dkr.ecr.us-east-1.amazonaws.com/tag_video:latest"
    subscribe_tags        = "539913718279.dkr.ecr.us-east-1.amazonaws.com/subscribe_tags:latest"
    unsubscribe_tags      = "539913718279.dkr.ecr.us-east-1.amazonaws.com/unsubscribe_tags:latest"
  }
}

variable "lambda_timeouts" {
  description = "Optional Lambda timeout override per function."
  type        = map(number)

  default = {
    change_visibility     = 30
    create_query_file_job = 30
    delete_file           = 30
    edit_tags             = 30
    get_private_media     = 30
    get_public_media      = 30
    get_query_file_job    = 30
    get_query_upload_url  = 30
    get_signed_url        = 30
    get_subscription      = 30
    get_upload_status     = 30
    media_ingest          = 900
    process_ml_result     = 60
    publish_tags          = 60
    query_file            = 300
    query_species         = 30
    query_tags            = 30
    query_thumbnail_url   = 30
    tag_image             = 300
    tag_video             = 900
    subscribe_tags        = 30
    unsubscribe_tags      = 30
  }
}

variable "lambda_memory_sizes" {
  description = "Optional Lambda memory size override per function."
  type        = map(number)

  default = {
    change_visibility     = 256
    create_query_file_job = 256
    delete_file           = 256
    edit_tags             = 256
    get_private_media     = 256
    get_public_media      = 256
    get_query_file_job    = 256
    get_query_upload_url  = 256
    get_signed_url        = 256
    get_subscription      = 256
    get_upload_status     = 256
    media_ingest          = 2048
    process_ml_result     = 512
    publish_tags          = 256
    query_file            = 1024
    query_species         = 256
    query_tags            = 256
    query_thumbnail_url   = 256
    tag_image             = 1024
    tag_video             = 2048
    subscribe_tags        = 256
    unsubscribe_tags      = 256
  }
}
