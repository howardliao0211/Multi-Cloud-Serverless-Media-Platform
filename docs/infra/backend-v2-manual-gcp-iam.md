# Backend v2 manual GCP IAM changes

For backend-v2 image media ingest testing, the existing GCP Workload Identity Federation setup was extended to allow the new AWS Lambda session name `media_ingest_v2`.

Manual changes applied:

1. Workload Identity Provider `aws-lambda` condition now allows both:
   - `arn:aws:sts::539913718279:assumed-role/aussie-eco-len-lambda-role/tag_image`
   - `arn:aws:sts::539913718279:assumed-role/aussie-eco-len-lambda-role/media_ingest_v2`

2. Service account `ael-us-aws-invoker@hazel-sphinx-490908-u6.iam.gserviceaccount.com` now grants both:
   - `roles/iam.workloadIdentityUser`
   - `roles/iam.serviceAccountTokenCreator`

   to the `media_ingest_v2` AWS principal.

These changes should be moved into Terraform before backend-v2 is considered fully reproducible.
