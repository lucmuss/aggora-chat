from .base import *  # noqa: F403,F401

DEBUG = True
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "0.0.0.0"]
CELERY_TASK_ALWAYS_EAGER = True
