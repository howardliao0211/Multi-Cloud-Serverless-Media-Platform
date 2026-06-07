# Icon Mapping

Recommended icons from `docs/icons/` for the generated diagrams:

| Diagram element | Icon file |
| --- | --- |
| AWS Lambda functions | `Arch_AWS-Lambda_64@5x.png` |
| Amazon API Gateway | `Arch_Amazon-API-Gateway_64@5x.png` |
| Amazon Cognito | `Arch_Amazon-Cognito_64@5x.png` |
| Amazon DynamoDB media/subscription tables | `Arch_Amazon-DynamoDB_64@5x.png` |
| Amazon SNS notifications | `Arch_Amazon-Simple-Notification-Service_64@5x.png` |
| Amazon S3 media bucket, prefixes, thumbnails, and model objects | `Arch_Amazon-Simple-Storage-Service_64@5x.png` |
| Google Cloud Run ML processor | `CloudRun-512-color-rgb.png` |
| Security, WIF, IAM, HMAC, Secret Manager, Secrets Manager | `SecurityIdentity-512-color.png` |
| AI/ML inference | `AIMachineLearning-512-color.png` |
| Artifact Registry or deployment pipeline | `artifact_registry.png` or `DevOps-512-color.png` |
| Observability and logging | `Observability-512-color.png` |

Notes:

- Use the AWS Lambda icon for both v1 functions (`tag_image`, `tag_video`) and v2 functions (`media_ingest_v2`, `process_ml_result_v2`).
- Use the S3 icon for both media prefixes (`images/`, `videos/`, `images-v2/`, `videos-v2/`) and model objects (`models/model.pt`, `models/mdv5a.pt`).
- Use the security icon for both WIF/Google ID token and HMAC signing. In a detailed draw.io version, split labels should distinguish IAM authorization from HMAC request integrity.
