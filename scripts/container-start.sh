#!/bin/sh
set -eu

if [ "${AUTO_MIGRATE_ON_START:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi

if [ "${AUTO_SEED_ON_START:-0}" = "1" ]; then
  if [ "${SEED_SKIP_DEMO_CONTENT:-0}" = "1" ]; then
    python manage.py seed --skip-demo-content
  else
    python manage.py seed
  fi
fi

exec "$@"
