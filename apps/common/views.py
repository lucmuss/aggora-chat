from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse


def healthz(request):
    return JsonResponse(
        {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "search_backend": settings.SEARCH_BACKEND,
        }
    )
