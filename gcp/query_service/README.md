# GCP Query Service

This service runs on Google Cloud Run and provides the GCP side of the multi-cloud architecture.

## Responsibilities

- Store replicated AWS media metadata in Firestore.
- Provide query endpoints for the frontend.
- Later validate AWS Cognito JWTs for user-facing endpoints.

## Current endpoints

- `GET /`
- `GET /health`
- `POST /internal/replicate-media`
- `POST /query/tags`

## Local run

```bash
cd gcp/query_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export FIRESTORE_PROJECT_ID="hazel-sphinx-490908-u6"
export FIRESTORE_DATABASE="(default)"
export ENVIRONMENT="local"

uvicorn app.main:app --reload --port 8080
