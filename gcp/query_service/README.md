# GCP Query Service

This service will run on Google Cloud Run and provide the multi-cloud query API for Aussie EcoLens.

Planned endpoints:

- `GET /health`
- `POST /internal/replicate-media`
- `POST /query/tags`
- `POST /query/species`
- `POST /query/thumbnail`
- `POST /query/file`

The service will validate AWS Cognito JWTs and query replicated metadata from Firestore.
