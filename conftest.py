import os
from urllib.parse import quote

def _configure_pytest_environment():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")

    pytest_database_url = os.environ.get("PYTEST_DATABASE_URL", "").strip()
    if not pytest_database_url:
        db_name = os.environ.get("PYTEST_POSTGRES_DB", "aggora_db")
        db_user = os.environ.get("PYTEST_POSTGRES_USER", "aggora_user")
        db_password = os.environ.get(
            "PYTEST_POSTGRES_PASSWORD",
            "6c6bfb6b2cfd42f9fa9b7352c1b130888dccf1616ad56d4c",
        )
        db_host = os.environ.get("PYTEST_POSTGRES_HOST", "127.0.0.1")
        db_port = os.environ.get("PYTEST_POSTGRES_PORT", os.environ.get("POSTGRES_HOST_PORT", "5432"))
        pytest_database_url = (
            f"postgresql://{quote(db_user)}:{quote(db_password)}@{db_host}:{db_port}/{quote(db_name)}"
        )
    os.environ["DATABASE_URL"] = pytest_database_url

    os.environ["POSTGRES_DB"] = os.environ.get("PYTEST_POSTGRES_DB", "aggora_db")
    os.environ["POSTGRES_USER"] = os.environ.get("PYTEST_POSTGRES_USER", "aggora_user")
    os.environ["POSTGRES_PASSWORD"] = os.environ.get(
        "PYTEST_POSTGRES_PASSWORD",
        "6c6bfb6b2cfd42f9fa9b7352c1b130888dccf1616ad56d4c",
    )
    os.environ["POSTGRES_HOST"] = os.environ.get("PYTEST_POSTGRES_HOST", "127.0.0.1")
    os.environ["POSTGRES_PORT"] = os.environ.get(
        "PYTEST_POSTGRES_PORT",
        os.environ.get("POSTGRES_HOST_PORT", "5432"),
    )
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = os.environ.get("PYTEST_CELERY_TASK_ALWAYS_EAGER", "1")


def pytest_load_initial_conftests(*args, **kwargs):
    _configure_pytest_environment()


_configure_pytest_environment()
