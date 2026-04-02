import os


# Keep pytest independent from local docker-compose hostnames like `db`/`redis`.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
os.environ["DATABASE_URL"] = os.environ.get("PYTEST_DATABASE_URL", "sqlite:////tmp/aggora_pytest.sqlite3")
for key in (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "REDIS_CACHE_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
):
    os.environ[key] = os.environ.get(f"PYTEST_{key}", "")
