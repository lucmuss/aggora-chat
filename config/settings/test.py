import os

import dj_database_url

from .base import *  # noqa: F403,F401

DEBUG = False

PYTEST_DATABASE_URL = os.environ.get("PYTEST_DATABASE_URL", "").strip()
if not PYTEST_DATABASE_URL:
    pytest_postgres_db = os.environ.get("PYTEST_POSTGRES_DB", os.environ.get("POSTGRES_DB", "aggora_db"))
    pytest_postgres_user = os.environ.get("PYTEST_POSTGRES_USER", os.environ.get("POSTGRES_USER", "aggora_user"))
    pytest_postgres_password = os.environ.get(
        "PYTEST_POSTGRES_PASSWORD",
        os.environ.get("POSTGRES_PASSWORD", "6c6bfb6b2cfd42f9fa9b7352c1b130888dccf1616ad56d4c"),
    )
    pytest_postgres_host = os.environ.get("PYTEST_POSTGRES_HOST", "127.0.0.1")
    pytest_postgres_port = os.environ.get(
        "PYTEST_POSTGRES_PORT",
        os.environ.get("POSTGRES_HOST_PORT", os.environ.get("POSTGRES_PORT", "5432")),
    )
    PYTEST_DATABASE_URL = (
        f"postgresql://{pytest_postgres_user}:{pytest_postgres_password}"
        f"@{pytest_postgres_host}:{pytest_postgres_port}/{pytest_postgres_db}"
    )

DATABASES = {
    "default": dj_database_url.parse(
        PYTEST_DATABASE_URL,
        conn_max_age=0,
        ssl_require=False,
    )
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "aggora-pytest-cache",
    }
}
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
CELERY_TASK_ALWAYS_EAGER = True
STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
