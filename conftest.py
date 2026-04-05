import os


# Keep pytest independent from local docker-compose hostnames like `db`.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
os.environ["DATABASE_URL"] = os.environ.get("PYTEST_DATABASE_URL", "sqlite:////tmp/aggora_pytest.sqlite3")
for key in (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
):
    os.environ[key] = os.environ.get(f"PYTEST_{key}", "")
os.environ["CELERY_TASK_ALWAYS_EAGER"] = os.environ.get("PYTEST_CELERY_TASK_ALWAYS_EAGER", "1")
