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
    ./scripts/dev-up.sh

dev-up:
    ./scripts/dev-up.sh

dev-down:
    docker compose --env-file environment.env -f docker-compose.dev.yml down

dev-logs:
    docker compose --env-file environment.env -f docker-compose.dev.yml logs -f web db

dev-ps:
    docker compose --env-file environment.env -f docker-compose.dev.yml ps

db-export:
    DUMP_DIR=/srv/projects/web/aggora-chat/dumps ./scripts/db-export-custom.sh

db-import:
    ./scripts/db-import-custom.sh

db-restore:
    ./scripts/db-import-custom.sh

db-import-latest:
    FORCE=1 ./scripts/db-import-custom.sh

db-dump-list:
    ls -lh dumps/*.dump

db-shell:
    docker compose --env-file environment.env -f docker-compose.dev.yml exec db psql -U $$(awk -F= '$$1=="POSTGRES_USER" {print $$2}' environment.env | tail -n 1 | sed 's/\r$$//; s/^"//; s/"$$//; s/^'\''//; s/'\''$$//') -d $$(awk -F= '$$1=="POSTGRES_DB" {print $$2}' environment.env | tail -n 1 | sed 's/\r$$//; s/^"//; s/"$$//; s/^'\''//; s/'\''$$//')

# Start Docker deployment simulation
stack-up:
    docker compose -f docker-compose.stack.yml up -d --build

# Install requirements via uv
sync:
    uv pip install -r requirements/base.txt
    uv pip install -r requirements/dev.txt

# Run Django tests
test:
    uv run python manage.py test

# Run pytest-based test collection
pytest:
    uv run pytest

# Create pre-commit hooks
setup:
    uv pip install pre-commit ruff mypy
    uv run pre-commit install
