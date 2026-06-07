# Current Implementation Audit

Audit date: 2026-06-07  
Audited commit: `3a317e3bda0e1ecf2a3e93b9f43d9ce21a7171a8` (`fix: update deprecated Terraform AWS region attribute`)  
Branch: `main`  
Branch state: `HEAD...origin/main` was `0 0` after `git fetch origin`  
Working tree before audit files: clean

## Scope

This audit covers the current repository implementation and the deployed/read-only shape visible from the configured AWS and GCP accounts. It does not modify `docs/architecture.drawio`, source code, cloud resources, secrets, Terraform-managed resources, or deployments.

Files inspected at minimum:

- `backend-v2/aws/container_functions/media_ingest/app.py`
- `backend-v2/aws/layers/python/shared/gcp_ml_client.py`
- `backend-v2/aws/layers/python/shared/ml_contracts.py`
- `backend-v2/aws/layers/python/shared/ml_result_processor.py`
- `backend-v2/aws/functions/process_ml_result/app.py`
- `backend-v2/gcp/ml_processor/server.py`
- `backend-v2/scripts/deploy_container_function.sh`
- `backend-v2/scripts/deploy_function.sh`
- `backend-v2/scripts/deploy_gcp_ml_processor.sh`
- `terraform/main.tf`
- `terraform/locals.tf`
- `terraform/modules/iam_policy/main.tf`
- `terraform/modules/lambda_iam_role/main.tf`
- `terraform/modules/lambda_image_function/main.tf`
- `frontend/src/Screens/UploadScreen.tsx`
- `backend/functions/get_signed_url/app.py`
- `docs/architecture.drawio`, `docs/icons/`, `docs/infra/`, and `docs/assignment/`

## v1 Production Path Today

The current production-style AWS path remains v1:

1. React frontend calls API Gateway and Lambda API functions.
2. `get_signed_url` creates DynamoDB media records and presigned S3 PUT URLs.
3. The frontend uploads directly to S3 with metadata: `file_name`, `checksum`, and `owner_id`.
4. Live S3 bucket notifications are configured for:
   - `images/` -> Lambda `tag_image`
   - `videos/` -> Lambda `tag_video`
5. Tagging results update DynamoDB media records to `ready`.
6. Query APIs read DynamoDB and return presigned S3 URLs for private media/thumbnails.
7. DynamoDB Streams invoke notification publishing, which sends SNS messages for public media whose ready tags match subscription filters.

The live S3 notification check found no configured trigger for `images-v2/` or `videos-v2/`.

## v2 Side-by-Side Path Today

The v2 implementation is side-by-side and manual-invoke oriented:

1. An S3 object under `images-v2/` or `videos-v2/` can be supplied to `media_ingest_v2` using an S3 event-shaped payload.
2. `media_ingest_v2` reads S3 metadata and object headers.
3. It creates and uploads a thumbnail when supported.
4. It generates a presigned S3 media `input_url`.
5. It generates presigned model URLs for:
   - `models/model.pt` as `classifier`
   - `models/mdv5a.pt` as `detector`
6. It builds the GCP request contract, signs the canonical body with HMAC, mints a Google ID token using WIF when configured, and calls Cloud Run `/process-media`.
7. GCP Cloud Run verifies HMAC and relies on Cloud Run IAM for the bearer token check.
8. GCP downloads media and model files from presigned URLs, caches models by `model_version`, runs image/video inference, and returns tag counts.
9. `media_ingest_v2` invokes `process_ml_result_v2` when `PROCESS_ML_RESULT_FUNCTION_NAME` is configured, otherwise it processes locally.
10. `process_ml_result_v2` normalizes the result and writes the DynamoDB media record as `ready` or `failed`.

## AWS to GCP Request Contract Found

`GcpMlRequest` in `ml_contracts.py` and `call_gcp_ml_processor` in `gcp_ml_client.py` produce this request:

```json
{
  "request_id": "uuid",
  "media_type": "image|video",
  "input_url": "https://presigned-s3-media-url",
  "model_urls": {
    "classifier": "https://presigned-model-url",
    "detector": "https://presigned-model-url"
  },
  "model_version": "string",
  "sample_every_n_frames": 30,
  "max_frame": 30
}
```

`sample_every_n_frames` and `max_frame` are only included when non-null, and `media_ingest_v2` only sets them for videos. There is duplicated optional-field assignment in `gcp_ml_client.py`, but it does not change the emitted payload.

## GCP to AWS Response Contract Found

For images, `server.py` returns:

```json
{
  "request_id": "uuid",
  "tag_counts": {
    "A": 3,
    "B": 2
  }
}
```

For videos, `server.py` returns:

```json
{
  "request_id": "uuid",
  "tag_counts": {
    "A": 3,
    "B": 2
  },
  "frames": [
    {
      "frame_index": 0,
      "tag_counts": {
        "A": 1,
        "B": 2
      }
    }
  ]
}
```

Successful responses do not require a `status` field. `normalize_gcp_result_shape` treats a missing `status` as `ok` and maps top-level `tag_counts` into stored DynamoDB `tags`.

## Image Path

The image path matches expected behavior:

- `media_ingest_v2` creates an image thumbnail.
- It sends a presigned `input_url` and presigned model URLs to Cloud Run.
- Cloud Run runs `real_image_inference`.
- The response contains top-level `tag_counts`.
- `process_ml_result_v2` stores normalized top-level `tag_counts` as DynamoDB `tags`.

## Video Path

The video path matches expected behavior:

- `media_ingest_v2` creates a video thumbnail.
- Optional video controls are only sent if `GCP_VIDEO_SAMPLE_EVERY_N_FRAMES` or `GCP_VIDEO_MAX_FRAME` is set.
- Cloud Run samples one frame per second by default by using the detected FPS as the frame interval.
- If `max_frame` is absent, whole-video processing continues unless `GCP_VIDEO_MAX_SAMPLED_FRAMES` is configured in Cloud Run.
- Per-frame results are returned in `frames[]`.
- Top-level video `tag_counts` are max count per species across sampled frames, not a sum.

## Model Loading and Versioning

The current code matches the expected request-supplied model loading path:

- AWS presigns `models/model.pt` and `models/mdv5a.pt` from S3.
- GCP Cloud Run accepts `model_urls.classifier` and `model_urls.detector`.
- GCP downloads model files to `GCP_MODEL_CACHE_DIR/<model_version>/`.
- `get_tagger` caches initialized taggers by `(model_version, classifier_path, detector_path)`.

There is a backward-compatible fallback to `/models/model.pt` and `/models/mdv5a.pt` if request/env model URLs are missing. The current v2 AWS caller supplies model URLs, so the expected path does not rely on baked-in model files.

## IAM, WIF, and HMAC

The current code and live checks match the expected security behavior:

- AWS signs the canonical JSON body with `X-Timestamp` and `X-Signature`.
- AWS reads HMAC from `INTERNAL_HMAC_SECRET`, `INTERNAL_HMAC_SECRET_NAME`, or `GCP_ML_HMAC_SECRET_NAME`.
- GCP verifies the HMAC and rejects missing, stale, or invalid signatures.
- AWS can mint a Google ID token using a WIF credentials file and `GCP_INVOKER_SERVICE_ACCOUNT`.
- The live Cloud Run IAM policy grants `roles/run.invoker` to `serviceAccount:ael-us-aws-invoker@hazel-sphinx-490908-u6.iam.gserviceaccount.com`.

Live Lambda configuration check showed these secret-safe environment key sets:

- `media_ingest_v2`: `GCP_INVOKER_SERVICE_ACCOUNT`, `INTERNAL_HMAC_SECRET`, `GCP_MODEL_VERSION`, `GCP_CLOUD_RUN_AUDIENCE`, `GCP_ML_PROCESSOR_URL`, `PROCESS_ML_RESULT_FUNCTION_NAME`
- `process_ml_result_v2`: `MEDIA_TABLE_NAME`, `MEDIA_BUCKET_NAME`

No secret values were printed or recorded.

## Terraform Scope

Current Terraform configuration in `terraform/` is not IAM-only in a strict sense. The checked-in configuration creates:

- AWS IAM roles
- AWS IAM policies
- AWS IAM role policy attachments
- AWS Lambda image functions when `var.lambda_image_uris` contains non-empty image URIs

The current checked-in Terraform files do not define GCP resources, API Gateway, Cognito, S3 buckets, DynamoDB tables, or SNS topics.

Important drift/state risk: local Terraform state still contains GCP resources from older configuration, including Cloud Run, Artifact Registry, WIF, service accounts, and Secret Manager resources. The attempted plan reported `0 to add, 0 to change, 13 to destroy` for those stale GCP state resources before failing on missing AWS credentials. Do not run `terraform apply` until this state/config mismatch is deliberately resolved.

## Live Cloud Checks Run

Read-only checks were run using `backend-v2/.env`:

- `aws sts get-caller-identity`: succeeded for AWS account `539913718279`.
- `aws s3api get-bucket-notification-configuration`: succeeded; found only v1 `images/` and `videos/` notifications.
- `aws lambda get-function-configuration` for `media_ingest_v2`: succeeded; package type `Image`, timeout `120`, memory `2048`.
- `aws lambda get-function-configuration` for `process_ml_result_v2`: succeeded; runtime `python3.12`, package type `Zip`, timeout `60`, memory `1024`.
- `gcloud run services describe`: succeeded; service `aussie-eco-len-us-demo-ml-processor` was Ready with URL `https://aussie-eco-len-us-demo-ml-processor-jt3duqdrdq-uk.a.run.app`.
- `gcloud run services get-iam-policy`: succeeded; `roles/run.invoker` granted to the AWS invoker service account.

## Validation Checks

- `python3 -m py_compile` for the requested Python files: passed.
- `bash -n` for the requested v2 scripts: passed.
- `terraform -chdir=terraform validate`: passed after allowing Terraform to execute the installed AWS provider plugin.
- `terraform -chdir=terraform plan -out=tfplan`: did not complete cleanly. It refreshed existing GCP state, planned destruction of 13 stale GCP resources no longer present in configuration, then failed because no valid AWS credential source was available to the Terraform AWS provider. No apply was run.

## Gaps, Risks, and Diagram Assumptions

- v2 is not wired as an automatic S3 notification path in live S3 configuration. Diagrams show `images-v2/` and `videos-v2/` as manual invoke today, with a future notification shown only as optional/future.
- The frontend upload path currently uses `get_signed_url`, which builds v1 `images/` and `videos/` S3 keys through the shared `build_s3_key` utility. It does not route normal uploads to `images-v2/` or `videos-v2/`.
- `media_ingest_v2` contains unused local variables `sample_every_n_frames` and `max_frame` before building `GcpMlRequest`; behavior is unaffected.
- `gcp_ml_client.py` assigns optional video fields into the payload twice; behavior is unaffected.
- `server.py` has older helper functions for env-based model URLs/local fallback in addition to the active request model URL path.
- Terraform local state and current configuration diverge significantly for GCP resources. The generated diagrams include GCP resources because they exist in the runtime/deployment path, not because current Terraform defines them.
- Query and notification diagrams assume the existing API Gateway routes front the corresponding Lambda functions; API Gateway resource definitions are not present in the current Terraform configuration.
