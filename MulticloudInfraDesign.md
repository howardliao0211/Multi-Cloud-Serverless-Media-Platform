# Aussie EcoLens Multi-Cloud Infrastructure Design

## Purpose

This document describes the planned multi-cloud architecture for the Aussie EcoLens project. It is intended to guide implementation, Terraform structure, frontend hosting, DNS design, and the final report/demo explanation.

The selected architecture uses:

* **AWS** as the primary cloud for authentication, media ingestion, storage, processing, metadata source of truth, notifications, frontend hosting, CDN, and DNS.
* **GCP** as the secondary cloud for replicated metadata storage and query APIs.
* **Terraform** as the Infrastructure as Code tool for provisioning and documenting the AWS and GCP resources.

## Final Architecture Summary

```text
User Browser
    |
    v
Route 53 DNS
    |
    v
CloudFront
    |
    v
S3 Static Website Bucket / Frontend Bucket
    |
    v
React / Vite Frontend
    |
    +-- AWS Cognito authentication
    |
    +-- AWS API Gateway for upload, tag edit, delete, notifications
    |
    +-- GCP Cloud Run for query APIs

AWS Core Backend
    |
    +-- Cognito user pool and app client
    +-- API Gateway HTTP API
    +-- Lambda: register-user
    +-- Lambda: get_signed_url
    +-- Lambda: bulk tag update
    +-- Lambda: delete files
    +-- Lambda: notification subscribe/unsubscribe
    +-- S3 media bucket
    +-- S3 ObjectCreated trigger
    +-- Lambda container: upload_to_db
    +-- DynamoDB media metadata table
    +-- SNS tag notifications
    +-- CloudWatch logs

GCP Query Backend
    |
    +-- Cloud Run query service
    +-- Firestore replicated metadata database
    +-- Service account for Cloud Run
    +-- Optional Artifact Registry for container images
```

## Design Decision

We will implement the stronger multi-cloud design:

```text
Option B: Replicate metadata into GCP Firestore.
```

This means AWS remains the source of truth for upload and processing, while GCP stores a replicated copy of metadata for query/search operations.

This is stronger than a simple GCP proxy because GCP owns a real part of the system: query API and query database.

## Cloud Responsibility Split

| Capability                           | Cloud | Service                         |
| ------------------------------------ | ----- | ------------------------------- |
| User authentication                  | AWS   | Cognito                         |
| Frontend hosting                     | AWS   | S3 + CloudFront                 |
| DNS                                  | AWS   | Route 53                        |
| HTTPS certificates                   | AWS   | ACM                             |
| API entry point for upload/mutations | AWS   | API Gateway                     |
| File upload URL generation           | AWS   | Lambda `get_signed_url`         |
| User registration                    | AWS   | Lambda `register-user`          |
| Media storage                        | AWS   | S3 media bucket                 |
| Upload event trigger                 | AWS   | S3 event notification           |
| Media processing                     | AWS   | Lambda container `upload_to_db` |
| ML model execution                   | AWS   | Lambda container / model files  |
| Metadata source of truth             | AWS   | DynamoDB                        |
| Tag notifications                    | AWS   | SNS                             |
| Logs                                 | AWS   | CloudWatch                      |
| Replicated query metadata            | GCP   | Firestore                       |
| Query API                            | GCP   | Cloud Run                       |
| Query service container registry     | GCP   | Artifact Registry, optional     |

## Current Verified AWS Deployment

The current deployment already has the core AWS upload-processing spine working.

### AWS Account and Region

* AWS account ID: `539913718279`
* IAM user used locally: `ChungYu`
* Local AWS CLI profile: `AussieEcoLense`
* Main deployed region: `us-east-1`

### Cognito

* User pool name: `User pool - AussieEcoLens`
* User pool ID: `us-east-1_JefGiQ7lB`
* App client name: `AussieEcoLens`
* App client ID: `7umv70h1q682h6pogi6hhc1lpc`
* Client secret: none

### API Gateway

Invoke URL:

```text
https://1jpi28kbj7.execute-api.us-east-1.amazonaws.com
```

Currently deployed routes:

| Method | Path              | Auth | Purpose                          |
| ------ | ----------------- | ---- | -------------------------------- |
| GET    | `/`               | None | Root health check                |
| POST   | `/register-user`  | None | Create Cognito user              |
| POST   | `/get_signed_url` | JWT  | Generate presigned S3 upload URL |

### S3

Media bucket:

```text
aussie-eco-len-bucket-12345
```

Verified prefixes:

```text
images/
models/
thumbnails/
videos/
```

S3 event notification:

* Event: `s3:ObjectCreated:Put`
* Target Lambda: `upload_to_db`

### DynamoDB

Media metadata table:

```text
aussie-eco-len-media
```

Key schema:

| Attribute | Key type      |
| --------- | ------------- |
| `hash`    | Partition key |

### Lambda Functions

Currently deployed Lambda functions:

* `root`
* `register-user`
* `get_signed_url`
* `upload_to_db`

`upload_to_db` is a container image Lambda with:

* Package type: `Image`
* Memory size: `3000 MB`
* Timeout: `900 seconds`
* IAM role: `arn:aws:iam::539913718279:role/aussie-eco-len-lambda-role`

Confirmed successful log:

```text
Using device: cpu
Loaded model in 7.18 seconds
Finished processing media: 4782772f0a8adc7ac1864efdd982088109530582e3d5cdd61d76e6a2b1a35c3c
```

Known issue:

```text
TABLE_NAME currently appears as "\"aussie-eco-len-media\"" instead of "aussie-eco-len-media".
```

This should be cleaned up in deployment scripts or Terraform.

## Target Runtime Flow

### 1. User Authentication

```text
User opens frontend
    |
    v
React app uses AWS Amplify
    |
    v
AWS Cognito authenticates user
    |
    v
Frontend receives Cognito ID token
```

The same Cognito token is used for AWS API Gateway and GCP Cloud Run.

### 2. Media Upload

```text
User selects image/video
    |
    v
Frontend calculates SHA-256 hash
    |
    v
Frontend calls AWS API Gateway POST /get_signed_url
    |
    v
get_signed_url Lambda checks DynamoDB for duplicate hash
    |
    v
Lambda returns presigned S3 PUT URL
    |
    v
Frontend uploads file directly to S3
```

### 3. Automatic Processing

```text
S3 receives object
    |
    v
S3 ObjectCreated:Put event
    |
    v
upload_to_db Lambda container starts
    |
    +-- downloads uploaded file
    +-- generates thumbnail for images
    +-- extracts video frames if video
    +-- runs ML model
    +-- writes metadata to DynamoDB
    +-- sends replicated metadata to GCP
    +-- publishes SNS notification if watched tag appears
```

### 4. Metadata Replication to GCP

```text
upload_to_db Lambda
    |
    v
writes canonical metadata to DynamoDB
    |
    v
calls GCP Cloud Run replication endpoint
    |
    v
Cloud Run writes replicated record to Firestore
```

Recommended endpoint:

```text
POST /internal/replicate-media
```

This endpoint should be protected using a shared secret or signed service credential. For the assignment, a simple internal API key stored as an environment variable is acceptable if documented clearly.

### 5. Query Flow

```text
User submits query from frontend
    |
    v
Frontend calls GCP Cloud Run query API
    |
    v
Cloud Run validates AWS Cognito JWT
    |
    v
Cloud Run queries Firestore
    |
    v
Cloud Run returns matching media URLs/thumbnails
```

Query APIs should include:

```text
POST /query/tags
POST /query/species
POST /query/thumbnail
POST /query/file
```

## Frontend Hosting Design

We will use:

```text
S3 + CloudFront + Route 53
```

This gives a professional, Terraform-friendly hosting design.

### Frontend Hosting Flow

```text
Route 53 DNS record
    |
    v
CloudFront distribution
    |
    v
Private S3 frontend bucket
    |
    v
React/Vite static files
```

### Why S3 + CloudFront

* S3 stores the built static frontend files.
* CloudFront provides HTTPS, CDN caching, and SPA routing fallback.
* Route 53 provides DNS.
* ACM provides TLS certificate.
* Terraform can manage the full hosting stack.

### Frontend Build

The frontend is a Vite app.

Build command:

```bash
cd frontend
npm ci
npm run build
```

Build output:

```text
frontend/dist
```

The `frontend/dist` contents are uploaded to the frontend S3 bucket.

### SPA Routing

Because React is a single-page app, CloudFront should serve `index.html` for unknown routes.

Recommended CloudFront custom error responses:

```text
403 -> /index.html -> 200
404 -> /index.html -> 200
```

## DNS Design

Assuming a project domain such as:

```text
aussie-ecolens.com
```

Recommended subdomains:

| Domain                     | Target          | Purpose                   |
| -------------------------- | --------------- | ------------------------- |
| `app.aussie-ecolens.com`   | CloudFront      | Frontend website          |
| `api.aussie-ecolens.com`   | AWS API Gateway | AWS backend API, optional |
| `query.aussie-ecolens.com` | GCP Cloud Run   | GCP query API, optional   |

For the assignment, only `app` is essential. `api` and `query` can use generated provider URLs if time is limited.

### DNS Implementation

Route 53 hosted zone:

```text
aussie-ecolens.com
```

Records:

```text
app.aussie-ecolens.com
    A/AAAA Alias -> CloudFront distribution

api.aussie-ecolens.com
    A/AAAA Alias -> API Gateway custom domain, optional

query.aussie-ecolens.com
    CNAME -> GCP Cloud Run custom domain, optional
```

### Certificate Design

For CloudFront, ACM certificate must be created in:

```text
us-east-1
```

Certificate should include:

```text
app.aussie-ecolens.com
```

Optional SANs:

```text
api.aussie-ecolens.com
query.aussie-ecolens.com
```

If `query.aussie-ecolens.com` is mapped through GCP, certificate handling may be managed by GCP instead.

## CORS Design

Allowed frontend origins should include:

```text
http://localhost:5173
https://app.aussie-ecolens.com
https://<cloudfront-domain>
```

CORS must be configured for:

* AWS API Gateway
* S3 media bucket presigned uploads
* GCP Cloud Run query API

S3 CORS should allow:

```text
PUT
GET
HEAD
```

API Gateway / Cloud Run should allow:

```text
Authorization
Content-Type
```

## Authentication Across Clouds

AWS Cognito is the single identity provider.

### Cognito Issuer

```text
https://cognito-idp.us-east-1.amazonaws.com/us-east-1_JefGiQ7lB
```

### Cognito Audience

```text
7umv70h1q682h6pogi6hhc1lpc
```

### AWS Validation

AWS API Gateway uses a JWT authorizer:

```text
Issuer: Cognito issuer
Audience: Cognito app client ID
```

### GCP Validation

GCP Cloud Run validates the same Cognito ID token manually using the Cognito JWKS endpoint:

```text
https://cognito-idp.us-east-1.amazonaws.com/us-east-1_JefGiQ7lB/.well-known/jwks.json
```

Required Cloud Run environment variables:

```text
COGNITO_ISSUER=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_JefGiQ7lB
COGNITO_AUDIENCE=7umv70h1q682h6pogi6hhc1lpc
FIRESTORE_PROJECT_ID=<gcp-project-id>
```

Frontend sends:

```http
Authorization: Bearer <Cognito ID token>
```

to both AWS and GCP APIs.

## Firestore Data Model

Firestore collection:

```text
media
```

Document ID:

```text
<media_hash>
```

Example document:

```json
{
  "hash": "sha256...",
  "media_type": "image",
  "original_key": "images/hash.jpg",
  "thumbnail_key": "thumbnails/hash.jpg",
  "original_url": "https://...",
  "thumbnail_url": "https://...",
  "tags": ["koala", "wombat"],
  "tag_counts": {
    "koala": 2,
    "wombat": 1
  },
  "status": "READY",
  "created_at": "2026-05-28T...",
  "updated_at": "2026-05-28T..."
}
```

### Query by Tags with Counts

Request:

```json
{
  "tags": {
    "koala": 1,
    "wombat": 2
  }
}
```

Required behaviour:

```text
Return files where koala >= 1 AND wombat >= 2.
```

This must be logical AND, not OR.

### Query by Species

Request:

```json
{
  "species": "dingo"
}
```

Required behaviour:

```text
Return all files where dingo count >= 1.
```

### Query by Thumbnail URL

Request:

```json
{
  "thumbnail_url": "https://..."
}
```

Required behaviour:

```text
Return the corresponding full-size image URL.
```

### Query by Uploaded File

Request:

```text
multipart/form-data with temporary query file
```

Required behaviour:

```text
Detect tags in the uploaded query file.
Do not permanently store the query file.
Find database files containing the detected tag set.
Return matching media URLs.
```

This can be implemented later if time allows.

## Metadata Replication Design

### Recommended Simple Design

The AWS `upload_to_db` Lambda should call a GCP Cloud Run internal replication endpoint after successfully writing to DynamoDB.

```text
AWS upload_to_db Lambda
    |
    | POST /internal/replicate-media
    v
GCP Cloud Run
    |
    v
Firestore media document
```

### Replication Request

```json
{
  "hash": "sha256...",
  "media_type": "image",
  "original_key": "images/hash.jpg",
  "thumbnail_key": "thumbnails/hash.jpg",
  "original_url": "https://...",
  "thumbnail_url": "https://...",
  "tags": ["koala"],
  "tag_counts": {
    "koala": 1
  },
  "status": "READY",
  "created_at": "2026-05-28T...",
  "updated_at": "2026-05-28T..."
}
```

### Replication Security

Minimum acceptable approach for assignment:

```text
AWS Lambda sends header:
X-Internal-Api-Key: <secret>

GCP Cloud Run validates this against environment variable:
INTERNAL_REPLICATION_API_KEY
```

Better approach if time allows:

```text
Use signed JWT/service account authentication between clouds.
```

## Terraform Structure

Recommended Terraform layout:

```text
terraform/
  versions.tf
  providers.tf
  variables.tf
  locals.tf
  outputs.tf

  aws_cognito.tf
  aws_frontend_hosting.tf
  aws_dns.tf
  aws_api_gateway.tf
  aws_lambda_iam.tf
  aws_lambda_functions.tf
  aws_s3.tf
  aws_dynamodb.tf
  aws_sns.tf

  gcp_providers.tf
  gcp_firestore.tf
  gcp_cloud_run.tf
  gcp_iam.tf
```

If the project grows, use modules:

```text
terraform/
  modules/
    aws-auth/
    aws-storage/
    aws-processing/
    aws-frontend/
    gcp-query/
  envs/
    dev/
```

For this assignment, file-per-concern is sufficient.

## Terraform AWS Resources

### Frontend Hosting

* `aws_s3_bucket.frontend`
* `aws_s3_bucket_public_access_block.frontend`
* `aws_cloudfront_distribution.frontend`
* `aws_cloudfront_origin_access_control.frontend`
* `aws_acm_certificate.frontend`
* `aws_acm_certificate_validation.frontend`
* `aws_route53_zone.main`
* `aws_route53_record.app`

### Media Storage

* `aws_s3_bucket.media`
* `aws_s3_bucket_cors_configuration.media`
* `aws_s3_bucket_notification.media_upload`

### Database

* `aws_dynamodb_table.media`
* Optional: `aws_dynamodb_table.subscriptions`
* Optional: `aws_dynamodb_table.tag_index`

### API and Auth

* `aws_cognito_user_pool.main`
* `aws_cognito_user_pool_client.frontend`
* `aws_apigatewayv2_api.main`
* `aws_apigatewayv2_authorizer.cognito`
* `aws_apigatewayv2_route.*`
* `aws_apigatewayv2_integration.*`
* `aws_apigatewayv2_stage.default`

### Lambda

* `aws_iam_role.lambda_exec`
* `aws_iam_role_policy.lambda_policy`
* `aws_lambda_function.get_signed_url`
* `aws_lambda_function.register_user`
* `aws_lambda_function.upload_to_db`
* `aws_lambda_permission.api_gateway`
* `aws_lambda_permission.s3_invoke_upload_to_db`

### Notifications

* `aws_sns_topic.tag_notifications`
* Optional: `aws_sns_topic_subscription.*`

## Terraform GCP Resources

* `google_project_service.run`
* `google_project_service.firestore`
* `google_project_service.artifactregistry`
* `google_firestore_database.default`
* `google_service_account.cloud_run_query`
* `google_cloud_run_v2_service.query`
* `google_cloud_run_service_iam_member.public_or_restricted`
* Optional: `google_artifact_registry_repository.query`

## Terraform Outputs

Recommended outputs:

```hcl
output "frontend_url" {
  value = "https://app.${var.domain_name}"
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.frontend.domain_name
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_user_pool_client_id" {
  value = aws_cognito_user_pool_client.frontend.id
}

output "aws_api_url" {
  value = aws_apigatewayv2_api.main.api_endpoint
}

output "media_bucket_name" {
  value = aws_s3_bucket.media.bucket
}

output "media_table_name" {
  value = aws_dynamodb_table.media.name
}

output "gcp_query_service_url" {
  value = google_cloud_run_v2_service.query.uri
}
```

## Frontend Environment Variables

For local development:

```env
VITE_COGNITO_USER_POOL_ID="us-east-1_JefGiQ7lB"
VITE_COGNITO_USER_POOL_CLIENT_ID="7umv70h1q682h6pogi6hhc1lpc"
VITE_API_URL="https://1jpi28kbj7.execute-api.us-east-1.amazonaws.com"
VITE_GCP_QUERY_API_URL="https://<cloud-run-url>"
```

For hosted frontend, these variables are injected at build time.

If using S3 + CloudFront static hosting, build locally or in CI and upload `frontend/dist` to S3.

## Deployment Phases

### Phase 1: Stabilise Current AWS System

* Confirm register works.
* Confirm login works.
* Confirm `/get_signed_url` works.
* Confirm S3 upload works.
* Confirm `upload_to_db` is triggered.
* Confirm DynamoDB metadata is written.
* Confirm thumbnails are generated.
* Fix `TABLE_NAME` environment variable quoting.

### Phase 2: Terraform Existing AWS Resources

* Codify or import current Cognito, S3, DynamoDB, API Gateway, Lambda, IAM, and S3 trigger resources.
* Add Terraform outputs for frontend env values.
* Keep current working cloud deployment stable while migrating to Terraform.

### Phase 3: Frontend Hosting and DNS

* Create frontend S3 bucket.
* Create CloudFront distribution.
* Configure ACM certificate.
* Configure Route 53 record for `app.<domain>`.
* Upload `frontend/dist` to S3.
* Configure CloudFront SPA fallback.
* Update CORS for hosted frontend domain.

### Phase 4: GCP Firestore and Cloud Run

* Create GCP project resources.
* Enable Cloud Run and Firestore APIs.
* Deploy Cloud Run query service.
* Create Firestore database.
* Add Cognito JWT validation to Cloud Run.
* Add internal replication endpoint.
* Add query endpoints.

### Phase 5: Metadata Replication

* Update AWS `upload_to_db` Lambda to call GCP replication endpoint.
* Store replicated records in Firestore.
* Verify AWS DynamoDB and GCP Firestore records match.
* Add retry/error handling or at least clear logging.

### Phase 6: Missing Assignment APIs

* Query by tags/counts/species.
* Query by thumbnail URL.
* Query by uploaded file.
* Bulk tag add/remove.
* Delete files.
* Tag-based SNS notifications.
* Video processing verification.

## Demo Narrative

The final demo should explain:

1. Users authenticate with AWS Cognito.
2. The React frontend is hosted on S3 and delivered through CloudFront with Route 53 DNS.
3. The frontend uses Cognito tokens to call protected AWS APIs.
4. The upload flow uses checksums and presigned S3 URLs.
5. S3 automatically triggers a container Lambda after upload.
6. The Lambda generates thumbnails, runs ML tagging, and writes metadata to DynamoDB.
7. Metadata is replicated to GCP Firestore.
8. Query requests are handled by GCP Cloud Run.
9. Cloud Run validates the same Cognito JWT, proving cross-cloud authentication.
10. Query results are returned from Firestore and displayed in the frontend.
11. AWS SNS handles tag-based notifications.

## Key Risks

| Risk                                                | Impact                           | Mitigation                                                                        |
| --------------------------------------------------- | -------------------------------- | --------------------------------------------------------------------------------- |
| GCP replication fails                               | Query data missing               | Log replication errors and keep DynamoDB as source of truth                       |
| Firestore data becomes stale                        | Query results inconsistent       | Use updated_at timestamps and re-replication on updates                           |
| CORS misconfiguration                               | Frontend cannot call APIs/upload | Maintain explicit allowed origins for localhost and production domain             |
| CloudFront SPA routing issue                        | Refreshing frontend route fails  | Add 403/404 fallback to `/index.html`                                             |
| Cognito token validation in GCP fails               | Query API unusable               | Validate issuer, audience, expiry, and JWKS carefully                             |
| Terraform importing existing resources is difficult | Infra drift                      | Start documenting existing resources, then gradually import or recreate dev stack |
| TABLE_NAME env var has extra quotes                 | Runtime confusion                | Fix Lambda environment variable in deployment                                     |

## Immediate Next Actions

1. Verify frontend register/login/upload through browser.
2. Inspect DynamoDB item after upload.
3. Inspect thumbnail output in S3.
4. Decide domain name for Route 53.
5. Create Terraform file structure.
6. Codify current AWS resources or plan Terraform imports.
7. Design GCP Cloud Run query service API contract.
8. Design Firestore document schema.
9. Implement metadata replication endpoint.
10. Connect frontend query screen to GCP query API.
