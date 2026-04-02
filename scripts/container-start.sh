#!/bin/sh
set -eu

if [ "${WAIT_FOR_DB_ON_START:-1}" = "1" ]; then
  python - <<'PY'
import os
import sys
import time
from urllib.parse import urlparse

host = os.environ.get("POSTGRES_HOST", "").strip()
port = int(os.environ.get("POSTGRES_PORT", "5432") or 5432)
database_url = os.environ.get("DATABASE_URL", "").strip()
if database_url:
    parsed = urlparse(database_url)
    if parsed.hostname:
        host = parsed.hostname
    if parsed.port:
        port = parsed.port

if not host:
    sys.exit(0)

for attempt in range(1, 31):
    try:
        import socket
        with socket.create_connection((host, port), timeout=2):
            print(f"Database reachable at {host}:{port}")
            sys.exit(0)
    except OSError:
        print(f"Waiting for database at {host}:{port} ({attempt}/30)")
        time.sleep(2)

print(f"Database did not become reachable at {host}:{port}", file=sys.stderr)
sys.exit(1)
PY
fi

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
