# GCP ML Processor

This is the GCP side of the multi-cloud ML processing architecture.

It runs as a Google Cloud Run service and exposes one main endpoint:

- `POST /process-media`

## Responsibility

GCP performs ML inference only.

AWS remains responsible for:

- Cognito authentication
- S3 upload and storage
- thumbnail generation
- video frame extraction
- DynamoDB source-of-truth metadata
- SNS notifications

## Request flow

1. AWS S3 receives an uploaded file.
2. AWS Lambda is triggered.
3. AWS Lambda prepares image/frame inputs.
4. AWS Lambda generates short-lived presigned S3 GET URLs.
5. AWS Lambda sends an HMAC-signed request to this Cloud Run service.
6. Cloud Run downloads the temporary URLs, runs inference, and returns tags/counts/detections.
7. AWS Lambda writes the authoritative result to DynamoDB.

## Security

`POST /process-media` requires:

- `X-Timestamp`
- `X-Signature`

The signature is:

```text
HMAC_SHA256(INTERNAL_HMAC_SECRET, timestamp + "." + raw_body)
