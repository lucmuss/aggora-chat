#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

MEDIA_DIR=${MEDIA_DIR:-media}
DUMP_DIR=${DUMP_DIR:-dumps}
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BASENAME=${BASENAME:-media}
OUTPUT_FILE=${OUTPUT_FILE:-$DUMP_DIR/${BASENAME}-${TIMESTAMP}.tar.gz}
LATEST_FILE=${LATEST_FILE:-$DUMP_DIR/${BASENAME}-latest.tar.gz}

mkdir -p "$MEDIA_DIR" "$DUMP_DIR"

tar -czf "$OUTPUT_FILE" -C "$MEDIA_DIR" .
cp "$OUTPUT_FILE" "$LATEST_FILE"

cat <<EOF
Media archive created.

Archive file:
$OUTPUT_FILE

Latest alias:
$LATEST_FILE
EOF
