#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

ENV_FILE=${ENV_FILE:-environment.env}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.dev.yml}
DUMP_DIR=${DUMP_DIR:-dumps}
BASENAME=${BASENAME:-agora}
DUMP_FILE=${DUMP_FILE:-$DUMP_DIR/${BASENAME}-latest.dump}
FORCE=${FORCE:-0}

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Start with 'just up' or copy environment.env.example first." >&2
  exit 1
fi

if [ ! -f "$DUMP_FILE" ]; then
  echo "Dump file not found: $DUMP_FILE" >&2
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

if [ "$FORCE" != "1" ]; then
  echo "Importing will replace objects in database '$POSTGRES_DB' from $DUMP_FILE." >&2
  echo "Re-run with FORCE=1 to continue." >&2
  exit 1
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
  pg_restore --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB" <"$DUMP_FILE"

cat <<EOF
Custom dump restored.

Source file:
$DUMP_FILE

Database:
$POSTGRES_DB
EOF
