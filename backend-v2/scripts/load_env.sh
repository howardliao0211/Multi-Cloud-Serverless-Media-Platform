#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-backend-v2/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  echo "Create one with: cp backend-v2/.env.example backend-v2/.env"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "Loaded $ENV_FILE"
