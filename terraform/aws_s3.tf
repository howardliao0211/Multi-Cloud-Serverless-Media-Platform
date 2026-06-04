# Existing media bucket is looked up in aws_existing.tf:
# data "aws_s3_bucket" "media" { ... }

resource "aws_lambda_permission" "allow_s3_invoke_tag_image" {
  count = var.enable_s3_notifications ? 1 : 0

  statement_id  = "allow-s3-invoke-tag-image"
  action        = "lambda:InvokeFunction"
  function_name = "tag_image"
  principal     = "s3.amazonaws.com"
  source_arn    = data.aws_s3_bucket.media.arn
}

resource "aws_lambda_permission" "allow_s3_invoke_tag_video" {
  count = var.enable_s3_notifications ? 1 : 0

  statement_id  = "allow-s3-invoke-tag-video"
  action        = "lambda:InvokeFunction"
  function_name = "tag_video"
  principal     = "s3.amazonaws.com"
  source_arn    = data.aws_s3_bucket.media.arn
}

resource "aws_s3_bucket_notification" "media_uploads" {
  count  = var.enable_s3_notifications ? 1 : 0
  bucket = data.aws_s3_bucket.media.id

  lambda_function {
    id                  = "tag-image-on-upload"
    lambda_function_arn = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:tag_image"
    events              = ["s3:ObjectCreated:Post", "s3:ObjectCreated:Put"]
    filter_prefix       = "images/"
  }

  lambda_function {
    id                  = "tag-video-on-upload"
    lambda_function_arn = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:tag_video"
    events              = ["s3:ObjectCreated:Post", "s3:ObjectCreated:Put"]
    filter_prefix       = "videos/"
  }

  depends_on = [
    aws_lambda_permission.allow_s3_invoke_tag_image,
    aws_lambda_permission.allow_s3_invoke_tag_video,
  ]
}
