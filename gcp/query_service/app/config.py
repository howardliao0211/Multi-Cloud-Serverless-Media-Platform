import os


# These settings are injected by Terraform/Cloud Run environment variables.
# Local development can set the same names before starting uvicorn.
PROJECT_ID = os.getenv("FIRESTORE_PROJECT_ID")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE", "(default)")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
INTERNAL_API_KEY = os.getenv("INTERNAL_REPLICATION_API_KEY", "")
MEDIA_PUBLIC_BASE_URL = os.getenv("MEDIA_PUBLIC_BASE_URL", "").rstrip("/")
