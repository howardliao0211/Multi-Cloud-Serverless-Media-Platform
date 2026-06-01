# Aussie EcoLens Multi-Cloud Infrastructure Design

## Design Goal

Aussie EcoLens must be a serverless multi-cloud wildlife media platform. The system should allow authenticated users to upload images/videos, automatically process them with a species detection model, store searchable metadata, run query APIs, support tag management/delete workflows, and send tag-based notifications.

The recommended design maximises assignment marks by giving each cloud a meaningful role:

```text
AWS = secure ingestion, storage, source-of-truth metadata, notifications, frontend delivery
GCP = replicated query database, Cloud Run query API, optional serverless GPU ML inference
```

## Best Target Architecture

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
S3 frontend bucket
    |
    v
React / Vite frontend
    |
    +-- AWS Cognito for authentication
    +-- AWS API Gateway for upload and mutation APIs
    +-- GCP Cloud Run for query APIs

AWS Core
    |
    +-- Cognito user pool and app client
    +-- API Gateway HTTP API
    +-- Lambda: register-user
    +-- Lambda: get_signed_url
    +-- Lambda: tag edit
    +-- Lambda: delete files
    +-- Lambda: notification subscribe
    +-- S3 media bucket
    +-- S3 event trigger
    +-- Lambda container: upload_to_db or lightweight processor orchestrator
    +-- DynamoDB source-of-truth metadata table
    +-- SNS notifications
    +-- CloudWatch logs

GCP Core
    |
    +-- Cloud Run query service
    +-- Firestore replicated metadata database
    +-- Cloud Run optional GPU ML processor
    +-- Artifact Registry for Cloud Run images
    +-- Service accounts and IAM
```

## Current Implementation State

### AWS

The current AWS deployment already has a working ingestion/processing spine:

```text
Cognito
API Gateway
/register-user
/get_signed_url
S3 media bucket
DynamoDB table
S3 ObjectCreated trigger
upload_to_db Lambda container
```

Verified AWS resources:

```text
AWS account: 539913718279
Region: us-east-1
API Gateway: https://1jpi28kbj7.execute-api.us-east-1.amazonaws.com
Cognito user pool: us-east-1_JefGiQ7lB
Cognito app client: 7umv70h1q682h6pogi6hhc1lpc
S3 media bucket: aussie-eco-len-bucket-12345
DynamoDB table: aussie-eco-len-media
DynamoDB key: hash
Lambda: root, register-user, get_signed_url, upload_to_db
```

### GCP

The current GCP scaffold has:

```text
Project: hazel-sphinx-490908-u6
Cloud Run region: us-east4
Firestore location: nam5
Firestore database: (default), FIRESTORE_NATIVE
Cloud Run placeholder: aussie-eco-len-us-demo-query
GCP query service source: gcp/query_service
```

## Cloud Responsibility Split

| Capability | Recommended owner | Service |
|---|---|---|
| User authentication | AWS | Cognito |
| Frontend hosting | AWS | S3 + CloudFront + Route 53 |
| Upload API | AWS | API Gateway + Lambda |
| File storage | AWS | S3 |
| Upload trigger | AWS | S3 event notification |
| Source-of-truth metadata | AWS | DynamoDB |
| Tag notifications | AWS | SNS |
| Query metadata replica | GCP | Firestore |
| Query API | GCP | Cloud Run |
| Query service image registry | GCP | Artifact Registry |
| ML processing stable path | AWS | Lambda container |
| ML processing advanced path | GCP | Cloud Run GPU |
| Infrastructure as Code | Both | Terraform |

## Why This Split Is Strong

This is stronger than using GCP only as a proxy. GCP owns an important part of the application: metadata replication and query/search APIs. If GPU processing is implemented, GCP also owns the most compute-intensive workload.

```text
AWS handles the media lifecycle:
upload -> store -> trigger -> process -> source-of-truth metadata -> notifications

GCP handles query serving:
replicated metadata -> Cloud Run search APIs -> frontend results
```

## Authentication Across Clouds

AWS Cognito is the single identity provider.

AWS API Gateway validates Cognito JWTs natively.

GCP Cloud Run should validate the same Cognito JWT manually using the Cognito issuer/JWKS endpoint.

```text
COGNITO_ISSUER=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_JefGiQ7lB
COGNITO_AUDIENCE=7umv70h1q682h6pogi6hhc1lpc
```

Frontend sends the same header to both clouds:

```http
Authorization: Bearer <Cognito ID token>
```

This provides a clear cross-cloud security story.

## Upload Flow

```text
1. User signs in through Cognito.
2. Frontend calculates SHA-256 checksum.
3. Frontend calls AWS POST /get_signed_url.
4. Lambda checks DynamoDB for duplicate hash.
5. If new, Lambda returns presigned S3 PUT URL.
6. Browser uploads directly to S3.
7. S3 ObjectCreated event triggers processing.
8. Processing creates tags, thumbnails, and metadata.
9. DynamoDB receives source-of-truth record.
10. Metadata is replicated to GCP Firestore.
```

## Recommended ML Processing Options

### Option A: Stable AWS CPU Processing

```text
S3 event -> AWS upload_to_db Lambda container -> DynamoDB -> Firestore replica
```

This is the current stable path.

Pros:

- Already tested.
- Uses current S3 trigger.
- Low implementation risk.
- Fully serverless.

Cons:

- CPU-only.
- GCP role is mostly query/replica.

### Option B: Stronger GCP Cloud Run GPU Processing

```text
S3 event
  -> lightweight AWS Lambda orchestrator
  -> presigned S3 GET URL
  -> GCP Cloud Run GPU /process-media
  -> GCP runs ML inference and thumbnail/frame processing
  -> AWS writes DynamoDB source-of-truth
  -> Firestore replica updated
```

Pros:

- Stronger multi-cloud architecture.
- GCP handles compute-intensive ML inference.
- Still serverless.
- Better story for video/ML scalability.

Cons:

- More complex.
- Requires GCP GPU region/quota.
- Requires a separate GPU-compatible container.
- Higher cost if misconfigured.

Recommended team strategy:

```text
Keep Option A working as fallback.
Implement Option B only after query service and replication are stable.
```

## Data Model

### DynamoDB Source-of-Truth Record

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
  "manual_tags": ["nocturnal"],
  "status": "READY",
  "created_at": "2026-...",
  "updated_at": "2026-...",
  "version": 1,
  "replication_status": "SYNCED"
}
```

### Firestore Replica

Collection:

```text
media
```

Document ID:

```text
<hash>
```

The Firestore document should mirror the DynamoDB record closely enough to serve query APIs without calling AWS for every query.

## Database Synchronisation

The correct consistency model is:

```text
DynamoDB = authoritative source of truth
Firestore = eventually consistent query replica
```

Replication flow:

```text
AWS writes/updates DynamoDB
  -> AWS calls GCP Cloud Run /internal/replicate-media
  -> Cloud Run upserts Firestore media/{hash}
```

Use:

```text
hash as shared key
idempotent upsert
updated_at
version
replication_status
retry logic
scheduled reconciliation
```

Never claim both databases are always instantly consistent.

## Query APIs

GCP Cloud Run should expose:

```text
POST /query/tags
POST /query/species
POST /query/thumbnail
POST /query/file
```

### Query by Tags

Request:

```json
{
  "tags": {
    "koala": 3,
    "wombat": 1
  }
}
```

Required behaviour:

```text
koala >= 3 AND wombat >= 1
```

The logical operation must be AND, not OR.

### Query by Species

Request:

```json
{
  "species": "dingo"
}
```

Returns all media containing at least one dingo.

### Query by Thumbnail URL

Request:

```json
{
  "thumbnail_url": "https://..."
}
```

Returns the corresponding full-size image URL.

### Query by Uploaded File

Request:

```text
multipart/form-data query file
```

Required behaviour:

```text
Detect tags in temporary query file.
Do not permanently store the query file.
Return media records containing the detected tag set.
```

This can be implemented after `/query/tags`, `/query/species`, and `/query/thumbnail`.

## Mutation APIs

Mutation APIs should remain on AWS because AWS owns the source-of-truth data and S3 files.

```text
POST /tags/bulk
POST /files/delete
POST /notifications/subscribe
POST /notifications/unsubscribe
```

After each mutation, AWS should update DynamoDB first, then replicate the updated record/deleted status to Firestore.

## Delete Strategy

Prefer soft delete first:

```json
{
  "status": "DELETED",
  "deleted_at": "2026-..."
}
```

Then delete physical S3 objects and eventually remove/mark Firestore records.

Queries should ignore records where:

```text
status = DELETED
```

## Notifications

Use AWS SNS.

Recommended flow:

```text
User subscribes to tag
  -> subscription stored in DynamoDB
  -> SNS email subscription created/confirmed
  -> upload_to_db detects matching tag
  -> SNS notification is sent
```

SNS belongs naturally in AWS because upload processing and source-of-truth metadata are in AWS.

## Frontend Hosting and DNS

Recommended hosting:

```text
S3 frontend bucket -> CloudFront -> Route 53 -> app.<domain>
```

Recommended subdomains:

```text
app-us.<domain>       US demo frontend
api-us.<domain>       AWS API Gateway custom domain, optional
query-us.<domain>     GCP Cloud Run custom domain, optional

app-au.<domain>       Australia stack frontend, optional
api-au.<domain>       Australia AWS API, optional
query-au.<domain>     Australia GCP query API, optional
```

CloudFront must use an ACM certificate in `us-east-1`.

## Terraform Environments

Current env files:

```text
terraform/envs/us-demo.tfvars
terraform/envs/aus-demo.tfvars
```

US demo:

```text
AWS: us-east-1
GCP Cloud Run: us-east4
Firestore: nam5
```

Australia target:

```text
AWS: ap-southeast-2
GCP Cloud Run: australia-southeast1
Firestore: australia-southeast1
```

Changing region does not migrate resources in place. It provisions a new regional stack.

Recommended state strategy:

```text
Use separate Terraform workspaces or separate environment states for us-demo and aus-demo.
```

## Docker Images

The full system needs two real Docker images:

| Image | Runtime | Purpose |
|---|---|---|
| `upload_to_db` | AWS Lambda container | ML/media processing stable path |
| `query_service` | GCP Cloud Run | Replication and query APIs |

Optional third image if GPU ML is implemented separately:

| Image | Runtime | Purpose |
|---|---|---|
| `ml_processor` | GCP Cloud Run GPU | GPU ML/video processing |

The frontend does not need Docker. It should be built to static files and served by S3/CloudFront.

## Recommended Implementation Order

1. Keep existing AWS upload pipeline stable.
2. Deploy real GCP query service image to Cloud Run.
3. Implement `/internal/replicate-media`.
4. Implement `/query/tags` and `/query/species`.
5. Add AWS-to-GCP replication from `upload_to_db`.
6. Add `/query/thumbnail`.
7. Connect frontend query screen to GCP.
8. Add AWS tag edit/delete APIs.
9. Replicate tag edits/deletes to Firestore.
10. Add SNS notifications.
11. Add frontend tag/delete/notification screens.
12. Prototype GCP Cloud Run GPU ML processor if time permits.
13. Add S3 + CloudFront + Route 53 frontend hosting.
14. Produce official architecture diagram and final report material.

## Demo Narrative

Use this story for the architecture presentation:

```text
Aussie EcoLens uses AWS Cognito as the single identity provider. Users upload media through a React frontend. AWS API Gateway and Lambda generate presigned S3 upload URLs and prevent duplicate uploads using checksums. Uploaded files are stored in S3, which triggers serverless processing. The processing function detects wildlife species, generates thumbnails/video frames, and writes authoritative metadata to DynamoDB. Metadata is replicated to GCP Firestore, where a Cloud Run query service handles search APIs. The same Cognito JWT is validated across AWS and GCP. Terraform defines both clouds and supports US and Australia deployment configurations.
```

## Key Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Firestore replica becomes stale | Query results incomplete | DynamoDB source of truth, retry, reconciliation |
| Cloud Run GPU quota unavailable | GPU ML cannot run | Keep AWS CPU Lambda as fallback |
| CORS misconfiguration | Frontend calls fail | Explicit localhost and production origins |
| Query scan slow | Slow demo/query response | Use tag index later; demo scale scan acceptable |
| Region migration breaks URLs | Frontend/backend mismatch | Use Terraform outputs and DNS |
| Docker daemon not running locally | Local build fails | Start Docker Desktop |
| Terraform state drift | Plan surprises | Avoid manual console edits after Terraform manages resources |
| GCP placeholder and Terraform drift | Plan updates Cloud Run unexpectedly | Commit desired config and check plan before apply |

## Report Talking Points

- AWS Cognito is mandatory and is used as the single identity provider.
- AWS handles secure upload and source-of-truth data.
- GCP handles serverless query APIs and replicated metadata.
- Optional GCP Cloud Run GPU provides a high-quality path for serverless ML inference.
- DynamoDB and Firestore use eventual consistency, not unsafe dual-write assumptions.
- Terraform supports repeatable deployment and region portability.
- The US stack is the current demo environment; the Australia config demonstrates production-region portability.
