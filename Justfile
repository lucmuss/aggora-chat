set shell := ["bash", "-c"]

default:
    @just --list

# Format everything with Ruff
format:
    uv run ruff format .
    uv run ruff check --fix .

# Lint everything with Ruff
lint:
    uv run ruff check .
    uv run ruff format --check .

# Run pre-commit checks manually
check:
    uv run pre-commit run --all-files

# Start the recommended contributor Docker environment
up:
    ./scripts/bootstrap-local-docker.sh

local-up:
    ./scripts/bootstrap-local-docker.sh

local-down:
    docker compose --env-file .env -f docker-compose.local.yml down

local-logs:
    docker compose --env-file .env -f docker-compose.local.yml logs -f nginx web db minio minio-init

local-ps:
    docker compose --env-file .env -f docker-compose.local.yml ps

local-minio-logs:
    docker compose --env-file .env -f docker-compose.local.yml logs -f minio minio-init

local-minio-console-url:
    @port=$(sed -n "s/^MINIO_CONSOLE_PORT=//p" .env 2>/dev/null | tail -n 1 | tr -d "\"'"); echo "http://127.0.0.1:${port:-19001}"

db-export:
    ./scripts/db-export-custom.sh

db-import:
    ./scripts/db-import-custom.sh

db-restore:
    ./scripts/db-import-custom.sh

db-import-latest:
    FORCE=1 ./scripts/db-import-custom.sh

db-dump-list:
    ls -lh dumps/*.dump

db-shell:
    docker compose --env-file .env -f docker-compose.local.yml exec db psql -U $$(awk -F= '$$1=="POSTGRES_USER" {print $$2}' .env | tail -n 1 | sed 's/\r$$//; s/^"//; s/"$$//; s/^'\''//; s/'\''$$//') -d $$(awk -F= '$$1=="POSTGRES_DB" {print $$2}' .env | tail -n 1 | sed 's/\r$$//; s/^"//; s/"$$//; s/^'\''//; s/'\''$$//')

minio-up:
    docker compose --env-file .env -f docker-compose.local.yml up -d minio minio-init

minio-logs:
    docker compose --env-file .env -f docker-compose.local.yml logs -f minio minio-init

minio-console-url:
    @port=$(sed -n "s/^MINIO_CONSOLE_PORT=//p" .env 2>/dev/null | tail -n 1 | tr -d "\"'"); echo "http://127.0.0.1:${port:-19001}"

media-export:
    ./scripts/media-export.sh

media-import:
    ./scripts/media-import.sh

media-import-latest:
    FORCE=1 ./scripts/media-import.sh

media-list:
    ls -lh dumps/media-*.tar.gz

media-migrate-to-s3:
    uv run python manage.py migrate_media_to_object_storage

media-migrate-to-s3-dry-run:
    uv run python manage.py migrate_media_to_object_storage --dry-run

media-variants-backfill:
    uv run python manage.py backfill_optimized_media_variants

media-variants-backfill-dry-run:
    uv run python manage.py backfill_optimized_media_variants --dry-run

media-variants-cleanup:
    uv run python manage.py cleanup_optimized_media_variants

media-variants-cleanup-dry-run:
    uv run python manage.py cleanup_optimized_media_variants --dry-run

prod-up:
    docker compose --env-file .env -f docker-compose.prod.yml up -d --build

prod-down:
    docker compose --env-file .env -f docker-compose.prod.yml down

prod-logs:
    docker compose --env-file .env -f docker-compose.prod.yml logs -f nginx web minio

# Install requirements via uv
sync:
    uv pip install -r requirements.txt
    uv pip install -r requirements-dev.txt

# Run Django tests
test:
    uv run pytest

# Run pytest-based test collection
pytest:
    uv run pytest

# Create pre-commit hooks
setup:
    uv pip install pre-commit ruff mypy
    uv run pre-commit install
