#!/usr/bin/env bash

ENV_FILE="${1:-backend-v2/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  echo "Create one with: cp backend-v2/.env.example backend-v2/.env"
  return 1 2>/dev/null || exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# Avoid AWS CLI opening a pager in local dev shells.
export AWS_PAGER="${AWS_PAGER:-}"

echo "Loaded $ENV_FILE"
