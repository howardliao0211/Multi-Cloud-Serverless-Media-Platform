#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
ROLE_NAME="${ROLE_NAME:-aussie-eco-len-lambda-role}"

MEDIA_TABLE_NAME="${MEDIA_TABLE_NAME:-aussie-eco-len-media}"
BUCKET_NAME="${BUCKET_NAME:-aussie-eco-len-bucket-12345}"
SNS_TOPIC_NAME="${SNS_TOPIC_NAME:-image-tag-notifications}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

echo "Account ID: ${ACCOUNT_ID}"
echo "Creating/updating Lambda role: ${ROLE_NAME}"
echo "Media table: ${MEDIA_TABLE_NAME}"
echo "Bucket: ${BUCKET_NAME}"
echo "SNS topic: ${SNS_TOPIC_NAME}"

cat > /tmp/lambda-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

if aws iam get-role --role-name "${ROLE_NAME}" >/dev/null 2>&1; then
  echo "Role already exists: ${ROLE_NAME}"

  echo "Updating trust policy..."
  aws iam update-assume-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-document file:///tmp/lambda-trust-policy.json
else
  echo "Creating role: ${ROLE_NAME}"
  aws iam create-role \
    --role-name "${ROLE_NAME}" \
    --assume-role-policy-document file:///tmp/lambda-trust-policy.json >/dev/null
fi

echo "Attaching AWSLambdaBasicExecutionRole..."
aws iam attach-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

cat > /tmp/aussie-eco-len-lambda-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SNSImageTagNotificationsAccess",
      "Effect": "Allow",
      "Action": [
        "sns:Subscribe",
        "sns:SetSubscriptionAttributes",
        "sns:ListSubscriptionsByTopic",
        "sns:Unsubscribe",
        "sns:Publish",
        "sns:GetSubscriptionAttributes"
      ],
      "Resource": "arn:aws:sns:${AWS_REGION}:${ACCOUNT_ID}:${SNS_TOPIC_NAME}"
    },
    {
      "Sid": "DynamoDBMediaTableAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${MEDIA_TABLE_NAME}"
    },
    {
      "Sid": "DynamoDBStreamReadAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:DescribeStream",
        "dynamodb:GetRecords",
        "dynamodb:GetShardIterator",
        "dynamodb:ListStreams"
      ],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${MEDIA_TABLE_NAME}/stream/*"
    },
    {
      "Sid": "S3UploadedMediaReadAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::${BUCKET_NAME}/images/*",
        "arn:aws:s3:::${BUCKET_NAME}/videos/*",
        "arn:aws:s3:::${BUCKET_NAME}/thumbnails/*",
        "arn:aws:s3:::${BUCKET_NAME}/models/*",
        "arn:aws:s3:::${BUCKET_NAME}/query_uploads/*"
      ]
    },
    {
      "Sid": "S3UploadAndThumbnailWriteAccess",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::${BUCKET_NAME}/images/*",
        "arn:aws:s3:::${BUCKET_NAME}/videos/*",
        "arn:aws:s3:::${BUCKET_NAME}/thumbnails/*",
        "arn:aws:s3:::${BUCKET_NAME}/query_uploads/*"
      ]
    },
    {
      "Sid": "S3ListBucketLimitedAccess",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}",
      "Condition": {
        "StringLike": {
          "s3:prefix": [
            "images/*",
            "videos/*",
            "thumbnails/*",
            "models/*",
            "query_uploads/*"
          ]
        }
      }
    }
  ]
}
EOF

echo "Adding inline Lambda application policy..."
aws iam put-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-name aussie-eco-len-lambda-policy \
  --policy-document file:///tmp/aussie-eco-len-lambda-policy.json

ROLE_ARN="$(aws iam get-role \
  --role-name "${ROLE_NAME}" \
  --query "Role.Arn" \
  --output text)"

echo ""
echo "Done."
echo "Role ARN:"
echo "${ROLE_ARN}"
echo ""
echo "Export it with:"
echo "export LAMBDA_ROLE_ARN=\"${ROLE_ARN}\""
