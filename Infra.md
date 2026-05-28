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