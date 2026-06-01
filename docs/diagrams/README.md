# Architecture Diagrams

This folder is reserved for system architecture diagrams, deployment diagrams, and report/demo visuals.

Recommended diagrams to create:

1. **Current Deployment Diagram**
   - AWS Cognito
   - AWS API Gateway
   - AWS Lambda functions
   - S3 media bucket
   - DynamoDB
   - GCP Firestore
   - GCP Cloud Run placeholder/query service

2. **Target Multi-Cloud Architecture**
   - React frontend hosted by S3 + CloudFront + Route 53
   - AWS upload/storage/source-of-truth path
   - GCP Firestore replica and Cloud Run query API
   - Optional GCP Cloud Run GPU ML inference service

3. **Sequence Diagram**
   - Login
   - Upload
   - S3 trigger
   - AWS thumbnail/frame extraction
   - GCP ML inference
   - DynamoDB write
   - Firestore replication
   - Query results

Use official AWS and Google Cloud architecture icons in the final report.


For the refined target diagram, show AWS retaining S3 originals, thumbnails, and extracted video frames. Show GCP Cloud Run GPU receiving only short-lived presigned S3 image/frame URLs for ML inference and returning tag counts/detections to AWS.
