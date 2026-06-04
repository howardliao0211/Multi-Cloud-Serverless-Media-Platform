# backend-v2

Parallel backend for the new multi-cloud media processing pipeline.

Flow:

1. User uploads image/video to AWS S3.
2. S3 ObjectCreated event invokes `media_ingest_v2`.
3. `media_ingest_v2` generates a presigned S3 URL and calls GCP Cloud Run ML processor.
4. GCP processes the media and returns tag JSON.
5. `media_ingest_v2` invokes `process_ml_result_v2`.
6. `process_ml_result_v2` updates DynamoDB and final media status.

The existing `backend/` remains untouched as the working rollback/demo path.
