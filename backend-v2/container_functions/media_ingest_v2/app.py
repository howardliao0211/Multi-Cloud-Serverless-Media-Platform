def lambda_handler(event, context):
    """
    Receive S3 upload events, generate timed S3 URLs, call GCP ML processor,
    and forward the returned tag JSON to process_ml_result_v2.

    This is a placeholder for the v2 backend pipeline.
    """
    return {
        "statusCode": 501,
        "body": "media_ingest_v2 not implemented yet",
    }
