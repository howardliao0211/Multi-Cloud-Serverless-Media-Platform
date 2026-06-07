aws_region = "us-east-1"

project_name = "aussie-eco-len"

bucket_name = "aussie-eco-len-bucket-12345"

media_table_name = "aussie-eco-len-media"

subscription_table_name = "aussie-eco-len-subscriptions"

sns_topic_name = "image-tag-notifications"

lambda_timeouts = {
  query_file = 900
  tag_image  = 900
  tag_video  = 900
}

lambda_memory_sizes = {
  query_file = 3008
  tag_image  = 3008
  tag_video  = 3008
}

lambda_image_uris = {
  query_file = "539913718279.dkr.ecr.us-east-1.amazonaws.com/aussie-ecolens-query-file:ml-dev"
  tag_image  = "539913718279.dkr.ecr.us-east-1.amazonaws.com/aussie-ecolens-tag-image:gcp-ml-dev"
  tag_video  = "539913718279.dkr.ecr.us-east-1.amazonaws.com/aussie-ecolens-tag-video:ml-dev"
}
