# Aussie EcoLens Infrastructure Notes

This document records the currently verified infrastructure state, local setup commands, and the next implementation steps for the Aussie EcoLens multi-cloud/serverless assignment.

## Current Architecture Position

Aussie EcoLens is a serverless wildlife media platform. The system supports authenticated users uploading images/videos, automatic media processing, ML-based species tagging, thumbnail generation, metadata storage, query APIs, tag management, file deletion, and notifications.

The current implementation is moving toward this split:

```text
AWS = authentication, upload gateway, media storage, source-of-truth metadata, notifications, frontend hosting
GCP = Cloud Run services, Firestore metadata replica, query APIs, optional GPU ML processing
Terraform = shared Infrastructure as Code for both clouds
```

## Current Repository Structure

```text
.
├── backend
│   ├── container_function/upload_to_db
│   ├── functions/get_signed_url
│   ├── layers
│   └── scripts
├── docs
│   ├── assignment
│   ├── diagrams
│   └── infra
├── frontend
├── gcp
│   └── query_service
├── terraform
│   └── envs
└── test
```

## Local Tooling

Recommended local tools:

```bash
node -v
npm -v
python3 --version
terraform -version
aws --version
gcloud --version
docker --version
```

Recommended versions:

- Node.js 20+
- npm
- Python 3.11+
- Terraform 1.5+
- AWS CLI v2
- Google Cloud CLI
- Docker Desktop

## AWS CLI Setup

The local AWS profile used for this project is:

```text
AussieEcoLense
```

Credentials must not be committed to Git. Keep access key CSV files outside the repo, or ensure they are ignored by `.gitignore`.

Check the active identity:

```bash
aws sts get-caller-identity --profile AussieEcoLense
```

Expected AWS account:

```text
539913718279
```

For a terminal session:

```bash
export AWS_PROFILE=AussieEcoLense
aws sts get-caller-identity
```

## GCP CLI Setup

The current GCP account and project used for the US demo stack are:

```text
Account: cliu0201@student.monash.edu
Project: hazel-sphinx-490908-u6
```

Check:

```bash
gcloud auth list
gcloud config list
```

Required GCP APIs:

```bash
gcloud services enable run.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

Terraform uses Application Default Credentials for the Google provider:

```bash
gcloud auth application-default login
```

## Current Verified AWS Deployment

### AWS Region and Account

```text
AWS account ID: 539913718279
Primary demo region: us-east-1
Local AWS CLI profile: AussieEcoLense
```

### Cognito

```text
User pool name: User pool - AussieEcoLens
User pool ID: us-east-1_JefGiQ7lB
App client name: AussieEcoLens
App client ID: 7umv70h1q682h6pogi6hhc1lpc
Client secret: none
```

### API Gateway

Invoke URL:

```text
https://1jpi28kbj7.execute-api.us-east-1.amazonaws.com
```

Currently verified routes:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | None | Health/root test endpoint |
| POST | `/register-user` | None | Create Cognito user |
| POST | `/get_signed_url` | JWT | Generate presigned S3 upload URL |

Verified root test:

```bash
curl https://1jpi28kbj7.execute-api.us-east-1.amazonaws.com/
```

Expected response:

```json
"Hello from Lambda!"
```

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

S3 notification:

```text
s3:ObjectCreated:Put -> upload_to_db Lambda
```

Check notification config:

```bash
aws s3api get-bucket-notification-configuration \
  --bucket aussie-eco-len-bucket-12345 \
  --profile AussieEcoLense
```

### DynamoDB

Media metadata table:

```text
aussie-eco-len-media
```

Key schema:

| Attribute | Key type |
|---|---|
| `hash` | Partition key |

Check table:

```bash
aws dynamodb describe-table \
  --table-name aussie-eco-len-media \
  --region us-east-1 \
  --profile AussieEcoLense \
  --query "Table.{TableName:TableName,KeySchema:KeySchema,Status:TableStatus}"
```

### Lambda Functions

Verified Lambda functions:

```text
root
register-user
get_signed_url
upload_to_db
```

`upload_to_db` configuration:

```text
Package type: Image
Memory: 3000 MB
Timeout: 900 seconds
Runtime platform: x86_64
Role: arn:aws:iam::539913718279:role/aussie-eco-len-lambda-role
Log group: /aws/lambda/upload_to_db
```

Known issue:

```text
TABLE_NAME currently appears as "\"aussie-eco-len-media\"" instead of "aussie-eco-len-media".
```

This should be fixed later in Terraform/deployment scripts.

### Current AWS Flow

```text
Frontend
  -> Cognito login
  -> API Gateway /get_signed_url
  -> Lambda checks DynamoDB by file hash
  -> Lambda returns presigned S3 PUT URL
  -> Browser uploads file to S3
  -> S3 triggers upload_to_db
  -> upload_to_db runs ML processing
  -> metadata/thumbnails are written
```

## Current Verified GCP Deployment

### Project and Region

```text
GCP project: hazel-sphinx-490908-u6
Primary demo region: us-east4
Firestore location: nam5
```

### Firestore

Terraform has created a Firestore Native database:

```text
Database: (default)
Location: nam5
Type: FIRESTORE_NATIVE
Delete protection: disabled
```

Verify:

```bash
gcloud firestore databases list \
  --project hazel-sphinx-490908-u6
```

### Cloud Run Placeholder

Terraform has deployed a placeholder query service:

```text
Service: aussie-eco-len-us-demo-query
Region: us-east4
```

Check:

```bash
gcloud run services list \
  --project hazel-sphinx-490908-u6 \
  --region us-east4
```

Cloud Run should scale to zero while idle. `min-instances` should be unset or `0`.

```bash
gcloud run services describe aussie-eco-len-us-demo-query \
  --region us-east4 \
  --project hazel-sphinx-490908-u6 \
  --format="value(spec.template.scaling.minInstanceCount)"
```

Blank output is acceptable and effectively means no minimum instances are configured.

## GCP Query Service Skeleton

Source code location:

```text
gcp/query_service
```

Current planned endpoints:

```text
GET  /
GET  /health
POST /internal/replicate-media
POST /query/tags
```

Local Docker build:

```bash
cd gcp/query_service
docker build -t aussie-ecolens-query .
```

Run locally:

```bash
docker run --rm -p 8080:8080 \
  -e FIRESTORE_PROJECT_ID="hazel-sphinx-490908-u6" \
  -e FIRESTORE_DATABASE="(default)" \
  -e ENVIRONMENT="local" \
  aussie-ecolens-query
```

Health check from another terminal:

```bash
curl http://localhost:8080/health
```

Expected response:

```json
{"status":"healthy"}
```

To stop a running local container:

```bash
docker ps
docker stop <CONTAINER_ID>
```

## Terraform

Terraform directory:

```text
terraform/
```

Important files:

```text
versions.tf
providers.tf
variables.tf
locals.tf
outputs.tf
aws_existing.tf
gcp_firestore.tf
gcp_cloud_run.tf
gcp_iam.tf
envs/us-demo.tfvars
envs/aus-demo.tfvars
```

Current Terraform strategy:

```text
1. Read existing AWS resources safely through data sources.
2. Manage new GCP Firestore and Cloud Run scaffold.
3. Later import or codify AWS resources gradually.
4. Support both US demo and Australia demo/prod-style stacks through tfvars.
```

Initialisation:

```bash
terraform -chdir=terraform init
```

Validate and plan US demo:

```bash
terraform -chdir=terraform fmt
terraform -chdir=terraform validate
terraform -chdir=terraform plan -var-file=envs/us-demo.tfvars
```

Apply US demo:

```bash
terraform -chdir=terraform apply -var-file=envs/us-demo.tfvars
```

Important Git behaviour:

- Commit `terraform/.terraform.lock.hcl`.
- Do not commit `terraform/.terraform/`.
- Do not commit `terraform/terraform.tfstate` or backups.

## Environment Strategy

Current demo environment:

```text
AWS: us-east-1
GCP Cloud Run: us-east4
GCP Firestore: nam5
```

Potential Australia environment:

```text
AWS: ap-southeast-2
GCP Cloud Run: australia-southeast1
GCP Firestore: australia-southeast1
```

Changing regions does not move resources in place. It creates a new regional stack. Use separate environment config and ideally separate Terraform state/workspaces.

## Recommended Final Multi-Cloud Target

The strongest target design for this assignment is:

```text
AWS:
  Cognito
  API Gateway
  S3 media bucket
  DynamoDB source-of-truth metadata
  SNS notifications
  S3 + CloudFront + Route 53 frontend hosting
  lightweight orchestration Lambdas

GCP:
  Cloud Run query API
  Firestore metadata replica
  Artifact Registry for service images
  optional Cloud Run GPU ML processor
```

Preferred long-term split:

```text
AWS = auth, upload, storage, source of truth, notifications
GCP = ML inference option, replicated metadata, query/search API
```

## Recommended ML Processing Decision

There are two possible ML processing designs.

### Stable Submission Path

Keep the existing AWS Lambda container `upload_to_db` as the primary ML processor.

Pros:

- Already tested.
- S3 trigger is already configured.
- Current model loading works.
- Lowest implementation risk.

Cons:

- CPU-only.
- Weaker multi-cloud story.

### Stronger Multi-Cloud Path

Move heavy ML processing to a GCP Cloud Run GPU service and keep AWS Lambda as a lightweight orchestrator.

Suggested flow:

```text
S3 ObjectCreated event
  -> AWS lightweight Lambda
  -> generate presigned S3 GET URL
  -> call GCP Cloud Run GPU /process-media
  -> GCP downloads media temporarily
  -> GCP runs ML inference / thumbnail / video frame extraction
  -> GCP returns tags/counts/output metadata
  -> AWS writes DynamoDB source-of-truth record
  -> AWS replicates metadata to GCP Firestore
```

This is the best architecture if GPU quota and implementation time allow. It is still serverless because Cloud Run is managed and can scale to zero.

Recommended project approach:

```text
1. Keep AWS CPU Lambda working as fallback.
2. Build GCP query service first.
3. Add Artifact Registry and deploy real Cloud Run query service.
4. If time allows, prototype GCP Cloud Run GPU ML processor.
5. Switch ML processing only after the GCP GPU path is stable.
```

## Database Synchronisation

Do not claim both databases are always perfectly synchronised. The correct model is:

```text
DynamoDB = source of truth
Firestore = eventually consistent query replica
```

Replication flow:

```text
AWS processing/mutation function
  -> write DynamoDB first
  -> call GCP Cloud Run /internal/replicate-media
  -> upsert Firestore media/{hash}
```

Recommended fields:

```json
{
  "hash": "sha256...",
  "updated_at": "2026-...",
  "version": 1,
  "replication_status": "SYNCED"
}
```

Reliability improvements:

```text
- Idempotent Firestore upsert by hash.
- updated_at/version checks to avoid stale overwrites.
- Basic retry when calling GCP.
- Scheduled reconciliation Lambda for failed/stale records.
```

## Missing Assignment Features

Still to implement:

```text
Query APIs:
  POST /query/tags
  POST /query/species
  POST /query/thumbnail
  POST /query/file

Mutation APIs:
  POST /tags/bulk
  POST /files/delete

Notifications:
  POST /notifications/subscribe
  POST /notifications/unsubscribe
  SNS tag-based email notifications

Frontend:
  query UI wired to GCP
  tag edit/delete UI
  notification UI
  thumbnail preview and click-through
```

## Next Engineering Steps

Recommended next steps:

```text
1. Add Artifact Registry Terraform resource.
2. Build and push gcp/query_service image.
3. Update Cloud Run Terraform image from placeholder to real image.
4. Test deployed /health on Cloud Run.
5. Test /internal/replicate-media against Firestore.
6. Implement /query/tags and /query/species fully.
7. Update frontend to use VITE_GCP_QUERY_API_URL.
8. Add AWS-to-GCP replication from upload_to_db.
9. Add tag edit/delete APIs on AWS.
10. Add SNS notifications.
```

## Useful Commands

Check AWS API routes:

```bash
aws apigatewayv2 get-routes \
  --api-id 1jpi28kbj7 \
  --region us-east-1 \
  --profile AussieEcoLense
```

Tail AWS processing logs:

```bash
aws logs tail /aws/lambda/upload_to_db \
  --region us-east-1 \
  --profile AussieEcoLense \
  --follow
```

Check GCP Cloud Run:

```bash
gcloud run services list \
  --project hazel-sphinx-490908-u6 \
  --region us-east4
```

Check local Git state:

```bash
git status
```
