# FIT5225_Ass2_AussieEcoLen

Aussie EcoLens is a multi-cloud/serverless wildlife observation platform for FIT5225 Assignment 2. The system is designed to support authenticated users uploading wildlife media, automatic cloud-side processing, thumbnail generation, ML-based species tagging, metadata storage, and later query/tag-management features.

## Repository Structure

text . ├── backend │   ├── container_function │   │   └── upload_to_db │   │       ├── DockerFile │   │       ├── lambda_function.py │   │       └── shared_layer/python/shared │   │           ├── model.py │   │           ├── model.pt │   │           ├── mdv5a.pt │   │           └── schemas.py │   ├── functions │   │   └── get_signed_url │   │       └── app.py │   ├── layers │   └── scripts ├── documents ├── frontend ├── terraform └── test 

## Prerequisites

Install the following tools before running the project locally:

bash node -v npm -v python3 --version terraform -version aws --version docker --version 

Recommended tools:

- Node.js 20+ or 22+
- npm
- Python 3.11 or 3.12
- Terraform
- AWS CLI v2
- Docker

On macOS, most tools can be installed with Homebrew:

bash brew install node terraform awscli docker 

## AWS CLI Setup

This project uses the AWS CLI profile name:

text AussieEcoLense 

If you have an IAM access key CSV file such as:

text ChungYu_accessKeys.csv 

make sure it is not committed to Git. The .gitignore should include:

gitignore *accessKeys*.csv .env .env.local *.tfstate *.tfstate.* 

The CSV file should look like this:

csv Access key ID,Secret access key AKIA...,xxxxxxxxxxxxxxxx 

From the project root, configure the AWS profile:

bash CSV="./ChungYu_accessKeys.csv"  ACCESS_KEY_ID=$(awk -F',' 'NR==2 {print $1}' "$CSV" | tr -d '\r"') SECRET_ACCESS_KEY=$(awk -F',' 'NR==2 {print $2}' "$CSV" | tr -d '\r"')  aws configure set aws_access_key_id "$ACCESS_KEY_ID" --profile AussieEcoLense aws configure set aws_secret_access_key "$SECRET_ACCESS_KEY" --profile AussieEcoLense aws configure set region ap-southeast-2 --profile AussieEcoLense aws configure set output json --profile AussieEcoLense aws configure set aws_session_token "" --profile AussieEcoLense 

Test the profile:

bash aws sts get-caller-identity --profile AussieEcoLense 

Expected account:

text 539913718279 

For the current terminal session, use:

bash export AWS_PROFILE=AussieEcoLense 

Confirm:

bash aws sts get-caller-identity 

## Terraform

Terraform configuration is located in:

text terraform/ 

Run:

bash cd terraform terraform init terraform fmt terraform validate terraform plan 

If the plan looks correct, apply it:

bash terraform apply 

Show Terraform outputs:

bash terraform output 

These outputs are used by the frontend and backend configuration, such as Cognito IDs and API URLs.

> Note: The current Terraform implementation may not yet provision the full backend infrastructure. It should eventually include Cognito, S3, DynamoDB, IAM roles, Lambda functions, API Gateway, S3 event triggers, SNS, and the secondary cloud component.

## Frontend

The frontend is located in:

text frontend/ 

Install dependencies:

bash cd frontend npm install 

Create a local environment file:

bash touch .env.local 

Example .env.local:

env VITE_COGNITO_USER_POOL_ID="<actual-user-pool-id>" VITE_COGNITO_USER_POOL_CLIENT_ID="<actual-client-id>" VITE_API_URL="<actual-api-gateway-url>" 

Build the frontend:

bash npm run build 

Run the local development server:

bash npm run dev 

The local site usually runs at:

text http://localhost:5173 

## Backend: Signed Upload URL Function

The signed upload URL function is located at:

text backend/functions/get_signed_url/app.py 

This function is responsible for:

- receiving file metadata and checksum,
- checking whether the file already exists,
- generating a presigned S3 upload URL,
- supporting upload deduplication.

Before deployment, check for hard-coded values:

bash grep -R "bucket\|table\|region\|ap-southeast\|Aussie" backend/functions/get_signed_url -n 

Ideally, bucket and table names should come from environment variables such as:

text MEDIA_BUCKET MEDIA_TABLE AWS_REGION 

## Backend: Upload Processing Container Function

The upload processing function is located at:

text backend/container_function/upload_to_db 

It contains the container-based Lambda code and bundled ML model files.

Build the Docker image locally:

bash docker build \   -f backend/container_function/upload_to_db/DockerFile \   -t aussie-ecolens-upload-to-db \   backend/container_function/upload_to_db 

This function is intended to be triggered by an S3 upload event. It should:

- read the uploaded file from S3,
- create an initial database record,
- generate thumbnails for images,
- run ML-based species tagging,
- update the database record with tags and processing status.

## Backend Deployment Scripts

Helper deployment scripts are located in:

text backend/scripts/ 

Make them executable:

bash chmod +x backend/scripts/*.sh 

Inspect scripts before running them:

bash cat backend/scripts/create_iam_role.sh cat backend/scripts/deploy_get_signed_url.sh cat backend/scripts/deploy_upload_to_db.sh 

Search for hard-coded configuration:

bash grep -R "BUCKET\|TABLE\|ROLE\|REGION\|ap-southeast\|aussie" backend/scripts backend/functions backend/container_function -n 

Only run deployment scripts after confirming the target AWS account, region, resource names, and IAM permissions.

## Test Media

Test files are located in:

text test/upload_to_s3/ 

Current test files:

text test_image.jpg test_video.mp4 upload_script.sh 

These can be used to test upload and S3-triggered processing once the backend infrastructure is deployed.

## Recommended Local Smoke Test

From the project root:

bash git status git check-ignore -v ChungYu_accessKeys.csv  aws sts get-caller-identity --profile AussieEcoLense  terraform -chdir=terraform init terraform -chdir=terraform validate terraform -chdir=terraform plan  npm --prefix frontend install npm --prefix frontend run build  docker build \   -f backend/container_function/upload_to_db/DockerFile \   -t aussie-ecolens-upload-to-db \   backend/container_function/upload_to_db 

## Security Notes

Do not commit:

- AWS access key CSV files,
- .env or .env.local,
- Terraform state files,
- private keys,
- local credentials,
- large local test media unless required.

Check ignored credential files:

bash git check-ignore -v ChungYu_accessKeys.csv 

If a credential file was accidentally tracked, remove it from Git tracking:

bash git rm --cached ChungYu_accessKeys.csv 

Then rotate the exposed access key in AWS IAM.

## Current Development Notes

The project currently has:

- a frontend React/Vite application,
- AWS Cognito-related Terraform,
- a signed upload URL Lambda,
- a container-based upload processing Lambda,
- bundled ML model files,
- local test media.

The remaining infrastructure should be expanded to include:

- S3 bucket and CORS,
- DynamoDB media metadata table,
- IAM roles and least-privilege policies,
- API Gateway routes,
- Cognito authorizer,
- Lambda permissions,
- S3 ObjectCreated trigger,
- SNS tag notifications,
- secondary cloud provider integration.

## Useful Commands

Check active AWS identity:

bash aws sts get-caller-identity 

Check active AWS profile:

bash echo $AWS_PROFILE 

Use the project profile:

bash export AWS_PROFILE=AussieEcoLense 

Run Terraform plan:

bash terraform -chdir=terraform plan 

Run frontend:

bash npm --prefix frontend run dev 

Build upload processing container:

bash docker build \   -f backend/container_function/upload_to_db/DockerFile \   -t aussie-ecolens-upload-to-db \   backend/container_function/upload_to_db 
## Current AWS Deployment Status

### AWS Account and Region

- AWS account ID: `539913718279`
- IAM user used locally: `ChungYu`
- Local AWS CLI profile: `AussieEcoLense`
- Main deployed region: `us-east-1`

### Frontend Local Environment

`frontend/.env.local`:

```env
VITE_COGNITO_USER_POOL_ID="us-east-1_JefGiQ7lB"
VITE_COGNITO_USER_POOL_CLIENT_ID="7umv70h1q682h6pogi6hhc1lpc"
VITE_API_URL="https://1jpi28kbj7.execute-api.us-east-1.amazonaws.com"
```

Local frontend URL:

```text
http://localhost:5173/
```

### Cognito

- User pool name: `User pool - AussieEcoLens`
- User pool ID: `us-east-1_JefGiQ7lB`
- App client name: `AussieEcoLens`
- App client ID: `7umv70h1q682h6pogi6hhc1lpc`
- Client secret: none
- ID token expiration: 60 minutes
- Access token expiration: 60 minutes
- Refresh token expiration: 5 days

### API Gateway

Invoke URL:

```text
https://1jpi28kbj7.execute-api.us-east-1.amazonaws.com
```

Currently deployed routes:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | None | Root health check |
| POST | `/register-user` | None | Create Cognito user |
| POST | `/get_signed_url` | JWT | Generate presigned S3 upload URL |

Verified root endpoint:

```bash
curl https://1jpi28kbj7.execute-api.us-east-1.amazonaws.com/
```

Expected response:

```json
"Hello from Lambda!"
```

### Lambda Functions

Currently deployed Lambda functions:

- `root`
- `register-user`
- `get_signed_url`
- `upload_to_db`

`upload_to_db` configuration:

- Package type: `Image`
- Memory size: `3000 MB`
- Timeout: `900 seconds`
- IAM role: `arn:aws:iam::539913718279:role/aussie-eco-len-lambda-role`
- Last checked status: triggered by S3 and successfully loads the ML model.

Known configuration issue:

```text
TABLE_NAME currently appears as "\"aussie-eco-len-media\"" instead of "aussie-eco-len-media".
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

S3 event notification:

- Event: `s3:ObjectCreated:Put`
- Target Lambda: `upload_to_db`

Confirmed flow:

```text
S3 object uploaded
→ S3 ObjectCreated:Put event
→ upload_to_db Lambda
→ ML processing / thumbnail / DynamoDB update
```

### DynamoDB

Media metadata table:

```text
aussie-eco-len-media
```

Verified table status:

```text
ACTIVE
```

Verified key schema:

| Attribute | Key type |
|---|---|
| `hash` | Partition key |

### Lambda Layer

Shared layer:

```text
arn:aws:lambda:us-east-1:539913718279:layer:aussie-eco-len-shared:2
```

Compatible runtime:

```text
python3.12
```

### Confirmed Working Flow

```text
Frontend local config
→ Cognito user pool/app client
→ API Gateway root endpoint
→ S3 bucket exists
→ DynamoDB table exists
→ Lambda layer exists
→ S3 can invoke upload_to_db
→ S3 ObjectCreated:Put triggers upload_to_db
→ upload_to_db loads ML model on CPU
→ upload_to_db completes media processing
```

Recent successful `upload_to_db` log:

```text
Using device: cpu
Loaded model in 7.18 seconds
Finished processing media: 4782772f0a8adc7ac1864efdd982088109530582e3d5cdd61d76e6a2b1a35c3c
```

### Currently Missing / Not Yet Deployed

- Query by tags/counts/species API
- Query by thumbnail URL API
- Query by uploaded query file API
- Bulk manual tag add/remove API
- Delete files API
- Tag-based notification API
- SNS notification workflow
- Multi-cloud provider integration
- Video processing verification

### Useful Verification Commands

```bash
aws sts get-caller-identity --profile AussieEcoLense
```

```bash
aws apigatewayv2 get-routes \
  --api-id 1jpi28kbj7 \
  --region us-east-1 \
  --profile AussieEcoLense
```

```bash
aws s3 ls s3://aussie-eco-len-bucket-12345 --profile AussieEcoLense
```

```bash
aws dynamodb describe-table \
  --table-name aussie-eco-len-media \
  --region us-east-1 \
  --profile AussieEcoLense \
  --query "Table.{TableName:TableName,KeySchema:KeySchema,Status:TableStatus}"
```

```bash
aws s3api get-bucket-notification-configuration \
  --bucket aussie-eco-len-bucket-12345 \
  --profile AussieEcoLense
```

```bash
aws logs tail /aws/lambda/upload_to_db \
  --region us-east-1 \
  --profile AussieEcoLense \
  --follow
```

```bash
aws logs tail /aws/lambda/get_signed_url \
  --region us-east-1 \
  --profile AussieEcoLense \
  --follow
```

### Next Verification Steps

1. Test registration through the local frontend.
2. Test login through the local frontend.
3. Upload `test/upload_to_s3/test_image.jpg` through the frontend.
4. Confirm `/get_signed_url` is called successfully.
5. Confirm the image appears in S3 under `images/`.
6. Confirm a thumbnail appears in S3 under `thumbnails/`.
7. Confirm the DynamoDB record is created or updated.
8. Confirm `upload_to_db` logs show successful processing.
9. Verify video upload behaviour.
10. Start planning missing query, tag-edit, delete, notification, and multi-cloud APIs.
