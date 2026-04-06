from django.conf import settings
from django.templatetags.static import static

from .seo import absolute_url


def branding(request):
    unread_count = 0
    theme_mode = request.COOKIES.get("agora_theme", "").strip().lower()
    if theme_mode not in {"light", "dark"}:
        if getattr(request.user, "is_authenticated", False):
            theme_mode = getattr(request.user, "preferred_theme", "light") or "light"
        else:
            theme_mode = "light"
    if getattr(request.user, "is_authenticated", False):
        unread_count = request.user.notifications.filter(is_read=False).count()
    default_og_image = absolute_url(static("icons/agora-logo.svg"))
    return {
        "APP_NAME": settings.APP_NAME,
        "APP_TAGLINE": settings.APP_TAGLINE,
        "APP_PUBLIC_URL": settings.APP_PUBLIC_URL,
        "APP_VERSION": settings.APP_VERSION,
        "APP_OG_IMAGE_URL": default_og_image,
        "COMPANY_NAME": settings.COMPANY_NAME,
        "COMPANY_SUPPORT_EMAIL": settings.COMPANY_SUPPORT_EMAIL,
        "COMPANY_SUPPORT_URL": settings.COMPANY_SUPPORT_URL,
        "seo_title": settings.APP_NAME,
        "seo_description": settings.APP_TAGLINE,
        "meta_robots": "index,follow",
        "canonical_url": absolute_url(request.path),
        "og_title": settings.APP_NAME,
        "og_description": settings.APP_TAGLINE,
        "og_type": "website",
        "og_image_url": default_og_image,
        "GOOGLE_AUTH_ENABLED": bool(getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}).get("google", {}).get("APP", {}).get("client_id")),
        "GITHUB_AUTH_ENABLED": bool(getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}).get("github", {}).get("APP", {}).get("client_id")),
        "unread_notifications_count": unread_count,
        "theme_mode": theme_mode,
    }
