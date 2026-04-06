from __future__ import annotations

from urllib.parse import urlsplit

from django.core.cache import cache
from django.http import HttpResponsePermanentRedirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings


class CanonicalHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        canonical_base = getattr(settings, "APP_PUBLIC_URL", "").strip()
        if not canonical_base:
            return self.get_response(request)

        parsed = urlsplit(canonical_base)
        canonical_host = parsed.netloc
        request_host = request.get_host()

        # Only normalize the common www -> apex case for the configured public host.
        if canonical_host and request_host == f"www.{canonical_host}":
            path = request.get_full_path()
            redirect_url = f"{parsed.scheme or 'https'}://{canonical_host}{path}"
            return HttpResponsePermanentRedirect(redirect_url)

        return self.get_response(request)


class HtmxRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        is_htmx_request = getattr(request, "htmx", False) or request.headers.get("HX-Request") == "true"
        if not is_htmx_request:
            return response

        location = response.headers.get("Location", "")
        login_path = urlsplit(str(settings.LOGIN_URL)).path or "/accounts/login/"
        redirected_to_login = (
            response.status_code in {301, 302, 303, 307, 308}
            and location
            and urlsplit(location).path.startswith(login_path)
        )
        if redirected_to_login:
            htmx_response = HttpResponse(status=204)
            htmx_response.headers["HX-Redirect"] = location
            return htmx_response

        return response


class SimpleRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != "POST":
            return self.get_response(request)

        bucket = self._bucket_for_request(request.path)
        if bucket is not None:
            limit, window = bucket
            ident = request.user.pk if getattr(request.user, "is_authenticated", False) else request.META.get("REMOTE_ADDR", "anon")
            cache_key = f"ratelimit:{request.path}:{ident}:{window}"
            current = cache.get(cache_key, 0) + 1
            cache.set(cache_key, current, timeout=window)
            if current > limit:
                if request.path.startswith("/api/"):
                    return JsonResponse({"error": "Too many requests. Slow down and try again shortly."}, status=429)
                return HttpResponse("Too many requests. Slow down and try again shortly.", status=429)

        return self.get_response(request)

    @staticmethod
    def _bucket_for_request(path: str):
        if path.startswith("/accounts/login/") or path.startswith("/accounts/signup/"):
            return (10, 300)
        if path.startswith("/api/v1/posts/") or path.startswith("/api/v1/comments/") or path.startswith("/vote/"):
            return (30, 60)
        if path.endswith("/toggle-join/") or path.endswith("/follow/") or path.endswith("/block/"):
            return (60, 60)
        if path.endswith("/submit/"):
            return (20, 60)
        return None
