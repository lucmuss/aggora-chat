#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

ENV_FILE=${ENV_FILE:-.env}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.local.yml}
DUMP_DIR=${DUMP_DIR:-dumps}
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BASENAME=${BASENAME:-agora}
OUTPUT_FILE=${OUTPUT_FILE:-$DUMP_DIR/${BASENAME}-${TIMESTAMP}.dump}
LATEST_FILE=${LATEST_FILE:-$DUMP_DIR/${BASENAME}-latest.dump}
ENV_EXAMPLE=${ENV_EXAMPLE:-.env.example}

mkdir -p "$DUMP_DIR"

if [ ! -f "$ENV_FILE" ]; then
  if [ -f "$ENV_EXAMPLE" ]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo "Created $ENV_FILE from $ENV_EXAMPLE"
  else
    echo "Missing $ENV_FILE. Start with 'just up' or copy .env.example first." >&2
    exit 1
  fi
fi

if ! docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps db >/dev/null 2>&1; then
  echo "The database service is not available in $COMPOSE_FILE." >&2
  exit 1
fi

read_env_value() {
  awk -F= -v key="$1" '$1==key {print $2}' "$ENV_FILE" | tail -n 1 | sed 's/\r$//; s/^"//; s/"$//; s/^'\''//; s/'\''$//'
}

POSTGRES_DB=$(read_env_value POSTGRES_DB)
POSTGRES_USER=$(read_env_value POSTGRES_USER)

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
