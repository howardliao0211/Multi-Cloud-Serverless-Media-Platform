#!/bin/bash
set -e

# Login
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1

aws ecr get-login-password --region "$REGION" | \
docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# Create repository
aws ecr create-repository --repository-name aussie_eco_len --region us-east-1 --image-scanning-configuration scanOnPush=true --image-tag-mutability MUTABLE

docker tag howardliao0211:upload_image 444177708053.dkr.ecr.us-east-1.amazonaws.com/aussie_eco_len:latest
