from .base import *  # noqa: F403,F401

DEBUG = False
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/tmp/aggora_pytest.sqlite3",
    }
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
