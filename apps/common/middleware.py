from __future__ import annotations

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse


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
