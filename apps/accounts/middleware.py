from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


class HandleRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        exempt_prefixes = (
            "/accounts/handle-setup/",
            "/accounts/logout/",
            "/accounts/google/",
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
