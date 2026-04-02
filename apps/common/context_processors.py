from django.conf import settings


def branding(request):
    unread_count = 0
    if getattr(request.user, "is_authenticated", False):
        unread_count = request.user.notifications.filter(is_read=False).count()
    return {
        "APP_NAME": settings.APP_NAME,
        "APP_TAGLINE": settings.APP_TAGLINE,
        "APP_PUBLIC_URL": settings.APP_PUBLIC_URL,
        "APP_VERSION": settings.APP_VERSION,
        "COMPANY_NAME": settings.COMPANY_NAME,
        "COMPANY_SUPPORT_EMAIL": settings.COMPANY_SUPPORT_EMAIL,
        "COMPANY_SUPPORT_URL": settings.COMPANY_SUPPORT_URL,
        "GOOGLE_AUTH_ENABLED": bool(getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}).get("google", {}).get("APP", {}).get("client_id")),
        "unread_notifications_count": unread_count,
    }
