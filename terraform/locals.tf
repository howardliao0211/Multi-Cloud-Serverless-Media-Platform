locals {
  lambda_names = toset([
    "change_visibility",
    "create_query_file_job",
    "delete_file",
    "edit_tags",
    "get_private_media",
    "get_public_media",
    "get_query_file_job",
    "get_query_upload_url",
    "get_signed_url",
    "get_subscription",
    "get_upload_status",
    "media_ingest",
    "process_ml_result",
    "publish_tags",
    "query_file",
    "query_species",
    "query_tags",
    "query_thumbnail_url",
    "tag_image",
    "tag_video",
    "subscribe_tags",
    "unsubscribe_tags"
  ])
}
