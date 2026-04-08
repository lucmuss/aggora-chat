#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

MEDIA_DIR=${MEDIA_DIR:-media}
DUMP_DIR=${DUMP_DIR:-dumps}
BASENAME=${BASENAME:-media}
ARCHIVE_FILE=${ARCHIVE_FILE:-$DUMP_DIR/${BASENAME}-latest.tar.gz}
FORCE=${FORCE:-0}

if [ ! -f "$ARCHIVE_FILE" ]; then
  echo "Media archive not found: $ARCHIVE_FILE" >&2
  exit 1
fi

mkdir -p "$MEDIA_DIR"

if [ "$FORCE" != "1" ] && find "$MEDIA_DIR" -mindepth 1 -print -quit | grep -q .; then
  echo "Media directory '$MEDIA_DIR' is not empty." >&2
  echo "Re-run with FORCE=1 to replace its contents." >&2
  exit 1
fi

if [ "$FORCE" = "1" ]; then
  find "$MEDIA_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
fi

tar -xzf "$ARCHIVE_FILE" -C "$MEDIA_DIR"

cat <<EOF
Media archive restored.

Source file:
$ARCHIVE_FILE

Media directory:
$MEDIA_DIR
EOF
