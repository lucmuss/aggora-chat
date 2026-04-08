#!/bin/sh
set -eu

MINIO_ALIAS=${MINIO_ALIAS:-localminio}
MINIO_ENDPOINT=${MINIO_ENDPOINT:-http://minio:9000}
MINIO_MEDIA_BUCKET=${MINIO_MEDIA_BUCKET:-${AWS_STORAGE_BUCKET_NAME:-agora-media}}
MINIO_ROOT_USER=${MINIO_ROOT_USER:-minioadmin}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD:-minioadmin123}

until mc alias set "$MINIO_ALIAS" "$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; do
  sleep 1
done

mc mb --ignore-existing "$MINIO_ALIAS/$MINIO_MEDIA_BUCKET"
mc anonymous set download "$MINIO_ALIAS/$MINIO_MEDIA_BUCKET"

echo "MinIO bucket ready: $MINIO_MEDIA_BUCKET"
