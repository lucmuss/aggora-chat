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

# Start Docker deployment simulation
up:
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
