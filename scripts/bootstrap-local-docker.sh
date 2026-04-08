#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

ENV_FILE=${ENV_FILE:-.env}
ENV_EXAMPLE=${ENV_EXAMPLE:-.env.example}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.local.yml}

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but was not found in PATH." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but the daemon is not reachable." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  if [ ! -f "$ENV_EXAMPLE" ]; then
    echo "Missing $ENV_FILE and $ENV_EXAMPLE." >&2
    exit 1
  fi
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "Created $ENV_FILE from $ENV_EXAMPLE"
fi

read_env_value() {
  awk -F= -v key="$1" '$1==key {print substr($0, index($0, "=")+1)}' "$ENV_FILE" \
    | tail -n 1 \
    | sed "s/\r$//; s/^\"//; s/\"$//; s/^'//; s/'$//"
}

APP_HOST_PORT=${APP_HOST_PORT:-$(read_env_value APP_HOST_PORT)}
POSTGRES_HOST_PORT=${POSTGRES_HOST_PORT:-$(read_env_value POSTGRES_HOST_PORT)}
MINIO_CONSOLE_PORT=${MINIO_CONSOLE_PORT:-$(read_env_value MINIO_CONSOLE_PORT)}
LOCAL_URL=${DOCKER_APP_PUBLIC_URL:-$(read_env_value DOCKER_APP_PUBLIC_URL)}
if [ -z "$LOCAL_URL" ]; then
  LOCAL_URL=${APP_PUBLIC_URL:-$(read_env_value APP_PUBLIC_URL)}
fi
POSTGRES_DB=${POSTGRES_DB:-$(read_env_value POSTGRES_DB)}
POSTGRES_USER=${POSTGRES_USER:-$(read_env_value POSTGRES_USER)}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-$(read_env_value POSTGRES_PASSWORD)}
MINIO_ROOT_USER=${MINIO_ROOT_USER:-$(read_env_value MINIO_ROOT_USER)}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD:-$(read_env_value MINIO_ROOT_PASSWORD)}

APP_HOST_PORT=${APP_HOST_PORT:-18080}
POSTGRES_HOST_PORT=${POSTGRES_HOST_PORT:-5432}
MINIO_CONSOLE_PORT=${MINIO_CONSOLE_PORT:-19001}
LOCAL_URL=${LOCAL_URL:-http://127.0.0.1:${APP_HOST_PORT}}
POSTGRES_DB=${POSTGRES_DB:-agora}
POSTGRES_USER=${POSTGRES_USER:-agora}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-agora_dev}
MINIO_ROOT_USER=${MINIO_ROOT_USER:-minioadmin}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD:-minioadmin123}

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up --build -d

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
  echo "Agora did not become healthy in time. Inspect with: docker compose --env-file $ENV_FILE -f $COMPOSE_FILE logs nginx web db minio" >&2
  exit 1
fi

cat <<EOF
Agora is running.

Open:
${LOCAL_URL}/

Health:
${LOCAL_URL}/healthz/

MinIO Console:
http://127.0.0.1:${MINIO_CONSOLE_PORT}/
username=${MINIO_ROOT_USER}
password=${MINIO_ROOT_PASSWORD}

Postgres:
localhost:${POSTGRES_HOST_PORT}
database=${POSTGRES_DB:-agora}
user=${POSTGRES_USER:-agora}
password=${POSTGRES_PASSWORD:-agora_dev}

Helpful commands:
docker compose --env-file ${ENV_FILE} -f ${COMPOSE_FILE} logs -f nginx web db minio
docker compose --env-file ${ENV_FILE} -f ${COMPOSE_FILE} down

Environment file:
${ENV_FILE}

Compose file:
${COMPOSE_FILE}
EOF
