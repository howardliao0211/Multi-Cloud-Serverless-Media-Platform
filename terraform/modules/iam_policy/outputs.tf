output "policy_arns" {
  description = "Reusable IAM policy ARNs."

  value = {
    s3_media_rw                  = aws_iam_policy.s3_media_rw.arn
    s3_read_media                = aws_iam_policy.s3_read_media.arn
    s3_write_media               = aws_iam_policy.s3_write_media.arn
    s3_put_upload_media          = aws_iam_policy.s3_put_upload_media.arn
    s3_put_query_uploads         = aws_iam_policy.s3_put_query_uploads.arn
    s3_put_thumbnails            = aws_iam_policy.s3_put_thumbnails.arn
    s3_delete_media              = aws_iam_policy.s3_delete_media.arn
    s3_delete_query_uploads      = aws_iam_policy.s3_delete_query_uploads.arn
    dynamodb_media_rw            = aws_iam_policy.dynamodb_media_rw.arn
    dynamodb_media_read          = aws_iam_policy.dynamodb_media_read.arn
    dynamodb_media_put           = aws_iam_policy.dynamodb_media_put.arn
    dynamodb_media_update        = aws_iam_policy.dynamodb_media_update.arn
    dynamodb_media_delete        = aws_iam_policy.dynamodb_media_delete.arn
    dynamodb_subscription_rw     = aws_iam_policy.dynamodb_subscription_rw.arn
    dynamodb_stream_read         = aws_iam_policy.dynamodb_stream_read.arn
    sns_publish                  = aws_iam_policy.sns_publish.arn
    sns_topic_manage             = aws_iam_policy.sns_subscription_manage.arn
    sns_subscription_manage      = aws_iam_policy.sns_subscription_manage.arn
    sns_subscription_read        = aws_iam_policy.sns_subscription_read.arn
    sns_subscription_subscribe   = aws_iam_policy.sns_subscription_subscribe.arn
    sns_subscription_unsubscribe = aws_iam_policy.sns_subscription_unsubscribe.arn
    invoke_query_file            = aws_iam_policy.invoke_query_file.arn
    lambda_invoke                = aws_iam_policy.lambda_invoke.arn
    secretsmanager_read          = aws_iam_policy.secretsmanager_read.arn
  }
}
