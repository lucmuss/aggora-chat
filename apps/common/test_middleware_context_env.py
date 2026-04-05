import pytest
import json
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory

from apps.accounts.models import Notification
from apps.common.celery import dispatch_task
from apps.common.context_processors import branding
from apps.common.middleware import SimpleRateLimitMiddleware
from config.env import _normalize_env_value, env_bool, env_float, env_int, env_list, env_str


User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "common_test_user"),
        "email": overrides.pop("email", "common_test_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "common_test_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


@pytest.mark.django_db
class TestCommonInfrastructure:
    def test_rate_limit_middleware_does_not_throttle_get_requests(self):
        cache.clear()
        middleware = SimpleRateLimitMiddleware(lambda request: HttpResponse("ok"))
        request = RequestFactory().get("/accounts/login/")
        request.user = make_user()

        responses = [middleware(request) for _ in range(12)]

        assert all(response.status_code == 200 for response in responses)

    def test_rate_limit_middleware_returns_html_429_for_login_posts(self):
        cache.clear()
        middleware = SimpleRateLimitMiddleware(lambda request: HttpResponse("ok"))
        request = RequestFactory().post("/accounts/login/")
        request.user = type("Anon", (), {"is_authenticated": False})()
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        for _ in range(10):
            assert middleware(request).status_code == 200

        blocked = middleware(request)

        assert blocked.status_code == 429
        assert "Too many requests" in blocked.content.decode()
        assert blocked["Content-Type"].startswith("text/html")

    def test_rate_limit_middleware_returns_json_429_for_api_paths(self):
        cache.clear()
        middleware = SimpleRateLimitMiddleware(lambda request: HttpResponse("ok"))
        request = RequestFactory().post("/api/v1/posts/")
        request.user = make_user(username="api_rl", email="api_rl@example.com", handle="api_rl")

        for _ in range(30):
            assert middleware(request).status_code == 200

        blocked = middleware(request)

        assert blocked.status_code == 429
        assert blocked["Content-Type"].startswith("application/json")
        assert json.loads(blocked.content.decode())["error"].startswith("Too many requests")

    def test_rate_limit_bucket_mapping_covers_expected_paths(self):
        assert SimpleRateLimitMiddleware._bucket_for_request("/accounts/login/") == (10, 300)
        assert SimpleRateLimitMiddleware._bucket_for_request("/accounts/signup/") == (10, 300)
        assert SimpleRateLimitMiddleware._bucket_for_request("/api/v1/posts/") == (30, 60)
        assert SimpleRateLimitMiddleware._bucket_for_request("/vote/") == (30, 60)
        assert SimpleRateLimitMiddleware._bucket_for_request("/u/test/follow/") == (60, 60)
        assert SimpleRateLimitMiddleware._bucket_for_request("/communities/submit/") == (20, 60)
        assert SimpleRateLimitMiddleware._bucket_for_request("/healthz/") is None

    def test_branding_context_processor_includes_auth_flags_and_unread_count(self, settings):
        settings.SOCIALACCOUNT_PROVIDERS = {
            "google": {"APP": {"client_id": "google-client"}},
            "github": {"APP": {"client_id": "github-client"}},
        }
        user = make_user(username="branding_user", email="branding_user@example.com", handle="branding_user")
        Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.POST_REPLY,
            message="Unread notification",
            url="/thread/1/",
            is_read=False,
        )
        Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.POST_REPLY,
            message="Read notification",
            url="/thread/2/",
            is_read=True,
        )
        request = RequestFactory().get("/")
        request.user = user

        context = branding(request)

        assert context["APP_NAME"]
        assert context["GOOGLE_AUTH_ENABLED"] is True
        assert context["GITHUB_AUTH_ENABLED"] is True
        assert context["unread_notifications_count"] == 1

    def test_branding_context_processor_handles_anonymous_user(self, settings):
        settings.SOCIALACCOUNT_PROVIDERS = {}
        request = RequestFactory().get("/")
        request.user = type("Anon", (), {"is_authenticated": False})()

        context = branding(request)

        assert context["GOOGLE_AUTH_ENABLED"] is False
        assert context["GITHUB_AUTH_ENABLED"] is False
        assert context["unread_notifications_count"] == 0

    @pytest.mark.parametrize(
        ("raw", "default", "expected"),
        [
            (None, "fallback", "fallback"),
            ("", "fallback", "fallback"),
            (" null ", "fallback", "fallback"),
            ("undefined", "fallback", "fallback"),
            ("${PLACEHOLDER}", "fallback", "fallback"),
            (" actual ", "fallback", "actual"),
        ],
    )
    def test_normalize_env_value_handles_placeholders_and_real_values(self, raw, default, expected):
        assert _normalize_env_value(raw, default) == expected

    def test_env_str_bool_int_float_and_list_parse_expected_values(self, monkeypatch):
        monkeypatch.setenv("ENV_STR_VALUE", "  hello  ")
        monkeypatch.setenv("ENV_BOOL_TRUE", "yes")
        monkeypatch.setenv("ENV_BOOL_FALSE", "undefined")
        monkeypatch.setenv("ENV_INT_VALUE", "42")
        monkeypatch.setenv("ENV_FLOAT_VALUE", "3.5")
        monkeypatch.setenv("ENV_LIST_VALUE", " alpha, beta ,, gamma ")

        assert env_str("ENV_STR_VALUE", "fallback") == "hello"
        assert env_bool("ENV_BOOL_TRUE", False) is True
        assert env_bool("ENV_BOOL_FALSE", True) is True
        assert env_int("ENV_INT_VALUE", 0) == 42
        assert env_float("ENV_FLOAT_VALUE", 0.0) == 3.5
        assert env_list("ENV_LIST_VALUE") == ["alpha", "beta", "gamma"]

    def test_dispatch_task_calls_function_directly_when_eager(self, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        calls = []

        def task(*args, **kwargs):
            calls.append((args, kwargs))
            return "sync-result"

        result = dispatch_task(task, 1, label="demo")

        assert result == "sync-result"
        assert calls == [((1,), {"label": "demo"})]

    def test_dispatch_task_uses_delay_when_not_eager(self, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = False
        calls = []

        class FakeTask:
            def __call__(self, *args, **kwargs):  # pragma: no cover
                raise AssertionError("Should not call task directly when not eager")

            def delay(self, *args, **kwargs):
                calls.append((args, kwargs))
                return "async-result"

        result = dispatch_task(FakeTask(), 2, label="queued")

        assert result == "async-result"
        assert calls == [((2,), {"label": "queued"})]
