from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.common.views import healthz, markdown_preview, service_worker, web_manifest
from apps.feeds.views import home, popular

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("manifest.webmanifest", web_manifest, name="web_manifest"),
    path("service-worker.js", service_worker, name="service_worker"),
    path("markdown/preview/", markdown_preview, name="markdown_preview"),
    path("", home, name="home"),
    path("popular/", popular, name="popular"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("apps.accounts.urls")),
    path("api/", include("apps.api.urls")),
    path("c/", include("apps.communities.urls")),
    path("", include("apps.search.urls")),
    path("", include("apps.moderation.urls")),
    path("", include("apps.posts.urls")),
    path("", include("apps.votes.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
