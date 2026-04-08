#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

ENV_FILE=${ENV_FILE:-environment.env}
ENV_EXAMPLE=${ENV_EXAMPLE:-environment.env.example}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.dev.yml}

if [ ! -f "$ENV_FILE" ]; then
  if [ ! -f "$ENV_EXAMPLE" ]; then
    echo "Missing $ENV_FILE and $ENV_EXAMPLE." >&2
    exit 1
  fi
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "Created $ENV_FILE from $ENV_EXAMPLE"
fi

APP_HOST_PORT=$(awk -F= '$1=="APP_HOST_PORT" {print $2}' "$ENV_FILE" | tail -n 1)
POSTGRES_HOST_PORT=$(awk -F= '$1=="POSTGRES_HOST_PORT" {print $2}' "$ENV_FILE" | tail -n 1)
APP_PUBLIC_URL=$(awk -F= '$1=="APP_PUBLIC_URL" {print $2}' "$ENV_FILE" | tail -n 1)

APP_HOST_PORT=${APP_HOST_PORT:-18080}
POSTGRES_HOST_PORT=${POSTGRES_HOST_PORT:-5432}
APP_PUBLIC_URL=${APP_PUBLIC_URL:-http://127.0.0.1:${APP_HOST_PORT}}

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up --build -d

echo "Waiting for Agora to become healthy at ${APP_PUBLIC_URL}/healthz/ ..."
i=0
until [ "$i" -ge 60 ]
do
  if curl -fsS "${APP_PUBLIC_URL}/healthz/" >/dev/null 2>&1; then
    break
  fi
  i=$((i + 1))
  sleep 2
done

if ! curl -fsS "${APP_PUBLIC_URL}/healthz/" >/dev/null 2>&1; then
  echo "Agora did not become healthy in time. Inspect with: docker compose --env-file $ENV_FILE -f $COMPOSE_FILE logs web db" >&2
  exit 1
fi

cat <<EOF
Agora is running.

Open:
${APP_PUBLIC_URL}/

Health:
${APP_PUBLIC_URL}/healthz/

Postgres:
localhost:${POSTGRES_HOST_PORT}

Environment file:
${ENV_FILE}

Compose file:
${COMPOSE_FILE}
EOF
