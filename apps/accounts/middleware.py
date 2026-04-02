import re

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from .security import user_requires_mfa


class HandleRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        exempt_prefixes = (
            "/accounts/handle-setup/",
            "/accounts/logout/",
            "/accounts/google/",
            "/accounts/github/",
            "/accounts/social/",
            "/admin/",
            "/static/",
            "/media/",
        )
        if (
            request.user.is_authenticated
            and not request.user.handle
            and not request.path.startswith(exempt_prefixes)
        ):
            return redirect("handle_setup")
        return self.get_response(request)


class StaffMfaEnforcementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self._community_settings_pattern = re.compile(r"^/c/[^/]+/settings/$")
        self._wiki_edit_pattern = re.compile(r"^/c/[^/]+/wiki(?:/[^/]+)?/edit/$")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        exempt_prefixes = (
            "/accounts/mfa/",
            "/accounts/login/",
            "/accounts/logout/",
            "/accounts/handle-setup/",
            "/admin/login/",
            "/static/",
            "/media/",
        )
        if request.path.startswith(exempt_prefixes):
            return self.get_response(request)

        sensitive_path = (
            request.path.startswith("/admin/")
            or request.path.startswith("/mod/")
            or request.path == "/c/create/"
            or bool(self._community_settings_pattern.match(request.path))
            or bool(self._wiki_edit_pattern.match(request.path))
        )
        if sensitive_path and user_requires_mfa(request.user):
            return redirect("account_mfa_setup")
        return self.get_response(request)
