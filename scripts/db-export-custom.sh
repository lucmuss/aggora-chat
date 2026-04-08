#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

ENV_FILE=${ENV_FILE:-environment.env}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.dev.yml}
DUMP_DIR=${DUMP_DIR:-dumps}
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BASENAME=${BASENAME:-agora}
OUTPUT_FILE=${OUTPUT_FILE:-$DUMP_DIR/${BASENAME}-${TIMESTAMP}.dump}
LATEST_FILE=${LATEST_FILE:-$DUMP_DIR/${BASENAME}-latest.dump}

mkdir -p "$DUMP_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Start with 'just up' or copy environment.env.example first." >&2
  exit 1
fi

if ! docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps db >/dev/null 2>&1; then
  echo "The database service is not available in $COMPOSE_FILE." >&2
  exit 1
fi

POSTGRES_DB=$(awk -F= '$1=="POSTGRES_DB" {print $2}' "$ENV_FILE" | tail -n 1)
POSTGRES_USER=$(awk -F= '$1=="POSTGRES_USER" {print $2}' "$ENV_FILE" | tail -n 1)

POSTGRES_DB=${POSTGRES_DB:-agora}
POSTGRES_USER=${POSTGRES_USER:-agora}

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc >"$OUTPUT_FILE"

cp "$OUTPUT_FILE" "$LATEST_FILE"

cat <<EOF
Custom dump created.

Dump file:
$OUTPUT_FILE

Latest alias:
$LATEST_FILE
EOF
