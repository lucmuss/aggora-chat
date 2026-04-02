from __future__ import annotations

import json

from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.templatetags.static import static
from django.views.decorators.http import require_GET, require_POST

from apps.common.markdown import render_markdown


@require_GET
def healthz(request):
    return JsonResponse(
        {
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "search_backend": settings.SEARCH_BACKEND,
        }
    )


@require_GET
def web_manifest(request):
    payload = {
        "name": settings.APP_NAME,
        "short_name": settings.APP_NAME,
        "description": settings.APP_TAGLINE,
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "display_override": ["window-controls-overlay", "standalone", "browser"],
        "background_color": "#f9fafb",
        "theme_color": "#0D9488",
        "icons": [
            {
                "src": static("icons/agora-icon.svg"),
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any maskable",
            }
        ],
    }
    return HttpResponse(json.dumps(payload), content_type="application/manifest+json")


@require_GET
def service_worker(request):
    script = f"""
const CACHE_NAME = "{settings.PROJECT_NAME}-shell-v{settings.APP_VERSION}";
const OFFLINE_URL = "/offline/";
const ASSETS = ["/", "/popular/", "/search/", OFFLINE_URL, "/manifest.webmanifest", "{static('css/app.css')}", "{static('js/app.js')}", "{static('icons/agora-icon.svg')}"];

self.addEventListener("install", (event) => {{
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))).then(() => self.clients.claim())
  );
}});

self.addEventListener("fetch", (event) => {{
  if (event.request.method !== "GET") {{
    return;
  }}
  if (event.request.mode === "navigate") {{
    event.respondWith(
      fetch(event.request)
        .then((response) => {{
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return response;
        }})
        .catch(() => caches.match(event.request).then((cached) => cached || caches.match(OFFLINE_URL)))
    );
    return;
  }}
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request).then((response) => {{
      const copy = response.clone();
      caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
      return response;
    }}).catch(() => caches.match(event.request).then((fallback) => fallback || caches.match(OFFLINE_URL))))
  );
}});
""".strip()
    return HttpResponse(script, content_type="application/javascript")


@require_POST
def markdown_preview(request):
    html = render_markdown((request.POST.get("markdown") or "").strip())
    if not html:
        html = "<p class='text-sm text-gray-400'>Nothing to preview yet.</p>"
    return HttpResponse(
        f"<div class='prose prose-sm max-w-none text-sm text-gray-700'>{html}</div>",
        content_type="text/html",
    )


@require_GET
def offline_page(request):
    return render(request, "offline.html", status=200)
