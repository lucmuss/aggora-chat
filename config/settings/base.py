from __future__ import annotations

import logging
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

from config.env import env_bool, env_float, env_int, env_list, env_str

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def _resolve_django_env() -> str:
    django_env = env_str("DJANGO_ENV", "development").strip().lower()
    if django_env not in {"development", "production"}:
        raise RuntimeError("DJANGO_ENV must be 'development' or 'production'.")
    return django_env


DJANGO_ENV = _resolve_django_env()
IS_PRODUCTION = DJANGO_ENV == "production"
PROJECT_NAME = env_str("PROJECT_NAME", "aggora-chat")
PROJECT_SLUG = env_str("PROJECT_SLUG", "aggora_chat")
APP_NAME = env_str("APP_NAME", "Agora")
APP_TAGLINE = env_str("APP_TAGLINE", "communities first")
APP_PUBLIC_URL = env_str("APP_PUBLIC_URL", "").rstrip("/")
APP_VERSION = env_str("APP_VERSION", "0.3.2")
SEED_USERS_FILE = env_str("SEED_USERS_FILE", "data/seed/users.json")
SEED_ADMINS_FILE = env_str("SEED_ADMINS_FILE", "data/seed/admins.json")
SEED_COMMUNITIES_FILE = env_str("SEED_COMMUNITIES_FILE", "data/seed/communities.json")
TEST_USER_EMAIL = env_str("TEST_USER_EMAIL", "").strip().lower()
TEST_USER_PASSWORD = env_str("TEST_USER_PASSWORD", "").strip()
TEST_USER_PHONE = env_str("TEST_USER_PHONE", "").strip()

SECRET_KEY = env_str("DJANGO_SECRET_KEY", "dev-only-secret-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", not IS_PRODUCTION)
ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    env_str("ALLOWED_HOSTS", "127.0.0.1,localhost"),
)
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    "allauth.socialaccount.providers.openid_connect",
    "django_htmx",
    "rest_framework",
    "rest_framework.authtoken",
    "apps.common",
    "django_elasticsearch_dsl",
    "apps.accounts",
    "apps.api",
    "apps.communities",
    "apps.feeds",
    "apps.moderation",
    "apps.posts",
    "apps.votes",
    "apps.search",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "apps.common.middleware.SimpleRateLimitMiddleware",
    "apps.accounts.middleware.HandleRequiredMiddleware",
    "apps.accounts.middleware.StaffMfaEnforcementMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.common.context_processors.branding",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = env_str("DATABASE_URL", "").strip()
if DATABASE_URL and not DATABASE_URL.startswith("${{"):
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=env_int("DATABASE_CONN_MAX_AGE", 60),
            ssl_require=env_bool("DATABASE_SSL_REQUIRE", False),
        )
    }
elif env_str("POSTGRES_DB", "").strip():
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env_str("POSTGRES_DB", "agora"),
            "USER": env_str("POSTGRES_USER", "agora"),
            "PASSWORD": env_str("POSTGRES_PASSWORD", "agora_dev"),
            "HOST": env_str("POSTGRES_HOST", "db"),
            "PORT": env_str("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": env_int("DATABASE_CONN_MAX_AGE", 60),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = env_str("DJANGO_LANGUAGE_CODE", "en-us")
TIME_ZONE = env_str("DJANGO_TIME_ZONE", "Europe/Berlin")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
SERVE_MEDIA_FILES = env_bool("SERVE_MEDIA_FILES", DEBUG)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SITE_ID = env_int("DJANGO_SITE_ID", 1)
AUTH_USER_MODEL = "accounts.User"

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = env_str("ACCOUNT_EMAIL_VERIFICATION", "optional")
ACCOUNT_PRESERVE_USERNAME_CASING = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
FORMS_URLFIELD_ASSUME_HTTPS = True
ACCOUNT_DEFAULT_HTTP_PROTOCOL = env_str(
    "ACCOUNT_DEFAULT_HTTP_PROTOCOL",
    "https" if IS_PRODUCTION else "http",
)
ACCOUNT_SIGNUP_FORM_CLASS = "apps.accounts.forms.SignupForm"
ACCOUNT_FORMS = {
    "reset_password": "apps.accounts.allauth_forms.StyledResetPasswordForm",
    "reset_password_from_key": "apps.accounts.allauth_forms.StyledResetPasswordKeyForm",
}
SOCIALACCOUNT_AUTO_SIGNUP = False

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": env_str("GOOGLE_CLIENT_ID", ""),
            "secret": env_str("GOOGLE_CLIENT_SECRET", ""),
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
    "github": {
        "APP": {
            "client_id": env_str("GITHUB_CLIENT_ID", ""),
            "secret": env_str("GITHUB_CLIENT_SECRET", ""),
        },
        "SCOPE": ["read:user", "user:email"],
    },
    "openid_connect": {
        "APPS": [],
    },
}

SEARCH_BACKEND = env_str("SEARCH_BACKEND", "sql").strip().lower()
if SEARCH_BACKEND not in {"sql", "elasticsearch"}:
    raise RuntimeError("SEARCH_BACKEND must be 'sql' or 'elasticsearch'.")
SEARCH_INDEX_ENABLED = SEARCH_BACKEND == "elasticsearch" and env_bool("SEARCH_INDEX_ENABLED", False)

ELASTICSEARCH_DSL = {
    "default": {"hosts": env_str("ELASTICSEARCH_URL", "http://elasticsearch:9200")},
}

CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", "memory://")
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", "cache+memory://")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_STORE_EAGER_RESULT = False

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "agora-local-cache",
    }
}

SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", IS_PRODUCTION)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = env_str("DJANGO_SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_AGE = env_int("DJANGO_SESSION_COOKIE_AGE", 1209600)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", IS_PRODUCTION)
CSRF_COOKIE_HTTPONLY = env_bool("DJANGO_CSRF_COOKIE_HTTPONLY", False)
CSRF_COOKIE_SAMESITE = env_str("DJANGO_CSRF_COOKIE_SAMESITE", "Lax")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", IS_PRODUCTION)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", True)
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000 if IS_PRODUCTION else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", IS_PRODUCTION)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", IS_PRODUCTION)
SECURE_REFERRER_POLICY = env_str("SECURE_REFERRER_POLICY", "same-origin")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

EMAIL_DELIVERY_MODE = env_str("EMAIL_DELIVERY_MODE", "console" if DEBUG else "smtp").lower()
EMAIL_BACKEND_MAP = {
    "smtp": "django.core.mail.backends.smtp.EmailBackend",
    "file": "django.core.mail.backends.filebased.EmailBackend",
    "console": "django.core.mail.backends.console.EmailBackend",
    "locmem": "django.core.mail.backends.locmem.EmailBackend",
}
EMAIL_BACKEND = env_str(
    "DJANGO_EMAIL_BACKEND",
    EMAIL_BACKEND_MAP.get(EMAIL_DELIVERY_MODE, "django.core.mail.backends.console.EmailBackend"),
)
EMAIL_FILE_PATH = str((BASE_DIR / env_str("EMAIL_FILE_PATH", "output/emails")).resolve())
EMAIL_HOST = env_str("DJANGO_EMAIL_HOST", env_str("EMAIL_HOST", "localhost"))
EMAIL_PORT = env_int("DJANGO_EMAIL_PORT", env_int("EMAIL_PORT", 25))
EMAIL_HOST_USER = env_str("DJANGO_EMAIL_HOST_USER", env_str("EMAIL_HOST_USER", ""))
EMAIL_HOST_PASSWORD = env_str("DJANGO_EMAIL_HOST_PASSWORD", env_str("EMAIL_HOST_PASSWORD", ""))
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", env_bool("EMAIL_USE_TLS", False))
EMAIL_USE_SSL = env_bool("DJANGO_EMAIL_USE_SSL", env_bool("EMAIL_USE_SSL", False))
EMAIL_TIMEOUT = env_int("DJANGO_EMAIL_TIMEOUT", 30)
DEFAULT_FROM_EMAIL = env_str(
    "DJANGO_DEFAULT_FROM_EMAIL",
    env_str("DEFAULT_FROM_EMAIL", "noreply@kolibri-kollektiv.eu"),
)
SERVER_EMAIL = env_str("DJANGO_SERVER_EMAIL", DEFAULT_FROM_EMAIL)

COMPANY_NAME = env_str("COMPANY_NAME", APP_NAME)
COMPANY_SUPPORT_EMAIL = env_str("COMPANY_SUPPORT_EMAIL", DEFAULT_FROM_EMAIL)
COMPANY_SUPPORT_URL = env_str(
    "COMPANY_SUPPORT_URL",
    f"{APP_PUBLIC_URL}/support" if APP_PUBLIC_URL else "",
)

APP_LOG_LEVEL = env_str("APP_LOG_LEVEL", "DEBUG" if DEBUG else "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": APP_LOG_LEVEL,
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": APP_LOG_LEVEL, "propagate": False},
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "60/minute",
        "anon": "20/minute",
    },
}

SENTRY_DSN = env_str("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        environment=env_str("SENTRY_ENVIRONMENT", DJANGO_ENV),
        release=env_str("SENTRY_RELEASE", ""),
        send_default_pii=env_bool("SENTRY_SEND_PII", False),
        debug=env_bool("SENTRY_DEBUG", False),
        traces_sample_rate=env_float("SENTRY_TRACES_SAMPLE_RATE", 0.0),
        profiles_sample_rate=env_float("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
    )
