#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but was not found in PATH." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but the daemon is not reachable." >&2
  exit 1
fi

APP_HOST_PORT=${APP_HOST_PORT:-18080}
POSTGRES_HOST_PORT=${POSTGRES_HOST_PORT:-5432}
LOCAL_URL=${APP_PUBLIC_URL:-http://127.0.0.1:${APP_HOST_PORT}}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.local.yml}

docker compose -f "$COMPOSE_FILE" up --build -d

echo "Waiting for Agora to become healthy at ${LOCAL_URL}/healthz/ ..."
i=0
until [ "$i" -ge 60 ]
do
  if curl -fsS "${LOCAL_URL}/healthz/" >/dev/null 2>&1; then
    break
  fi
  i=$((i + 1))
  sleep 2
done

if ! curl -fsS "${LOCAL_URL}/healthz/" >/dev/null 2>&1; then
  echo "Agora did not become healthy in time. Inspect with: docker compose -f $COMPOSE_FILE logs web db" >&2
  exit 1
fi

cat <<EOF
Agora is running.

Open:
${LOCAL_URL}/

Health:
${LOCAL_URL}/healthz/

Postgres:
localhost:${POSTGRES_HOST_PORT}
database=${POSTGRES_DB:-agora}
user=${POSTGRES_USER:-agora}
password=${POSTGRES_PASSWORD:-agora_dev}

Compose file:
${COMPOSE_FILE}
EOF
