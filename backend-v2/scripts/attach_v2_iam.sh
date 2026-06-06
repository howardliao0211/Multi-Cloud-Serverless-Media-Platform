#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_PROFILE="${AWS_PROFILE:-AussieEcoLense}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-539913718279}"
MEDIA_BUCKET_NAME="${MEDIA_BUCKET_NAME:-aussie-eco-len-bucket-12345}"
LAMBDA_ROLE_NAME="${LAMBDA_ROLE_NAME:-aussie-eco-len-lambda-role}"

PROCESS_ML_RESULT_FUNCTION_NAME="${PROCESS_ML_RESULT_FUNCTION_NAME:-process_ml_result_v2}"

POLICY_NAME="${POLICY_NAME:-backend-v2-runtime-access}"
POLICY_FILE="$(mktemp)"

cat > "$POLICY_FILE" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BackendV2ReadUploadedMedia",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:HeadObject"
      ],
      "Resource": [
        "arn:aws:s3:::${MEDIA_BUCKET_NAME}/images-v2/*",
        "arn:aws:s3:::${MEDIA_BUCKET_NAME}/videos-v2/*",
        "arn:aws:s3:::${MEDIA_BUCKET_NAME}/query-temp-v2/*"
      ]
    },
    {
      "Sid": "BackendV2WriteDerivedObjects",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::${MEDIA_BUCKET_NAME}/thumbnails/*",
        "arn:aws:s3:::${MEDIA_BUCKET_NAME}/query-temp-v2/*"
      ]
    },
    {
      "Sid": "BackendV2InvokeResultProcessor",
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${PROCESS_ML_RESULT_FUNCTION_NAME}"
    }
  ]
}
JSON

aws iam put-role-policy \
  --role-name "$LAMBDA_ROLE_NAME" \
  --policy-name "$POLICY_NAME" \
  --policy-document "file://${POLICY_FILE}" \
  --profile "$AWS_PROFILE"

rm -f "$POLICY_FILE"

echo "Attached ${POLICY_NAME} to ${LAMBDA_ROLE_NAME}"
