from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory

from apps.accounts.middleware import HandleRequiredMiddleware, StaffMfaEnforcementMiddleware
from apps.accounts.security import (
    build_totp_uri,
    generate_totp_secret,
    normalize_totp_code,
    user_requires_mfa,
    verify_totp,
)
from apps.communities.models import Community, CommunityMembership

User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "security_user"),
        "email": overrides.pop("email", "security_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", None),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug, creator):
    return Community.objects.create(
        name=slug.replace("-", " ").title(),
        slug=slug,
        title=slug.replace("-", " ").title(),
        description="Security tests",
        creator=creator,
    )


@pytest.mark.django_db
class TestSecurityHelpers:
    def test_generate_totp_secret_returns_non_empty_base32_value(self):
        secret = generate_totp_secret()

        assert len(secret) >= 16
        assert secret.upper() == secret

    @pytest.mark.parametrize(
        ("raw_code", "expected"),
        [
            ("123 456", "123456"),
            ("12-34-56", "123456"),
            ("abc123", "123"),
            ("", ""),
        ],
    )
    def test_normalize_totp_code_strips_to_digits(self, raw_code, expected):
        assert normalize_totp_code(raw_code) == expected

    def test_verify_totp_accepts_current_code_and_rejects_invalid_code(self):
        secret = generate_totp_secret()
        valid_counter_time = 1_700_000_000
        code = __import__("apps.accounts.security", fromlist=["_totp_at"])._totp_at(secret, valid_counter_time // 30)

        assert verify_totp(secret, code, at_time=valid_counter_time) is True
        assert verify_totp(secret, "000000", at_time=valid_counter_time) is False

    def test_build_totp_uri_includes_app_name_and_account(self, settings):
        settings.APP_NAME = "Agora"
        user = SimpleNamespace(email="uri@example.com", handle="uriuser", username="uriuser", mfa_totp_secret="SECRET123")

        uri = build_totp_uri(user)

        assert uri.startswith("otpauth://totp/Agora:")
        assert "secret=SECRET123" in uri
        assert "issuer=Agora" in uri

    def test_user_requires_mfa_for_staff_and_moderators_without_totp(self):
        plain_user = make_user(username="plain", email="plain@example.com", handle="plain")
        staff_user = make_user(username="staff", email="staff@example.com", handle="staff", is_staff=True)
        owner = make_user(username="owner", email="owner@example.com", handle="owner")
        community = make_community("mfa-community", owner)
        CommunityMembership.objects.create(user=owner, community=community, role=CommunityMembership.Role.OWNER)

        assert user_requires_mfa(plain_user) is False
        assert user_requires_mfa(staff_user) is True
        assert user_requires_mfa(owner) is True

        owner.mfa_totp_enabled = True
        owner.save(update_fields=["mfa_totp_enabled"])
        assert user_requires_mfa(owner) is False


@pytest.mark.django_db
class TestHandleRequiredMiddleware:
    def test_redirects_authenticated_user_without_handle(self):
        user = make_user(username="needshandle", email="needshandle@example.com", handle=None)
        request = RequestFactory().get("/")
        request.user = user
        middleware = HandleRequiredMiddleware(lambda request: HttpResponse("ok"))

        response = middleware(request)

        assert response.status_code == 302
        assert response.url.endswith("/accounts/handle-setup/")

    @pytest.mark.parametrize(
        "path",
        [
            "/accounts/handle-setup/",
            "/accounts/logout/",
            "/accounts/google/login/",
            "/accounts/github/login/",
            "/accounts/social/connections/",
            "/admin/",
            "/static/app.css",
            "/media/avatar.png",
        ],
    )
    def test_allows_exempt_paths(self, path):
        user = make_user(username="exempt", email="exempt@example.com", handle=None)
        request = RequestFactory().get(path)
        request.user = user
        middleware = HandleRequiredMiddleware(lambda request: HttpResponse("ok"))

        response = middleware(request)

        assert response.status_code == 200


@pytest.mark.django_db
class TestStaffMfaEnforcementMiddleware:
    @pytest.mark.parametrize(
        "path",
        [
            "/admin/",
            "/mod/sample/queue/",
            "/c/create/",
            "/c/sample/settings/",
            "/c/sample/wiki/edit/",
            "/c/sample/wiki/home/edit/",
        ],
    )
    def test_redirects_sensitive_paths_when_user_requires_mfa(self, path):
        user = make_user(username="staffmfa", email="staffmfa@example.com", handle="staffmfa", is_staff=True)
        request = RequestFactory().get(path)
        request.user = user
        middleware = StaffMfaEnforcementMiddleware(lambda request: HttpResponse("ok"))

        response = middleware(request)

        assert response.status_code == 302
        assert response.url.startswith("/accounts/mfa/?next=")

    @pytest.mark.parametrize(
        "path",
        [
            "/accounts/mfa/",
            "/accounts/login/",
            "/accounts/logout/",
            "/accounts/handle-setup/",
            "/admin/login/",
            "/static/app.css",
            "/media/avatar.png",
        ],
    )
    def test_exempt_paths_continue_without_redirect(self, path):
        user = make_user(username="exemptmfa", email="exemptmfa@example.com", handle="exemptmfa", is_staff=True)
        request = RequestFactory().get(path)
        request.user = user
        middleware = StaffMfaEnforcementMiddleware(lambda request: HttpResponse("ok"))

        response = middleware(request)

        assert response.status_code == 200

    def test_allows_sensitive_path_when_mfa_already_enabled(self):
        user = make_user(
            username="withmfa",
            email="withmfa@example.com",
            handle="withmfa",
            is_staff=True,
            mfa_totp_enabled=True,
        )
        request = RequestFactory().get("/admin/")
        request.user = user
        middleware = StaffMfaEnforcementMiddleware(lambda request: HttpResponse("ok"))

        response = middleware(request)

        assert response.status_code == 200
