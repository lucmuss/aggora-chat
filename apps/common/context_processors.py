from django.conf import settings


def branding(request):
    return {
        "APP_NAME": settings.APP_NAME,
        "APP_TAGLINE": settings.APP_TAGLINE,
        "APP_PUBLIC_URL": settings.APP_PUBLIC_URL,
        "APP_VERSION": settings.APP_VERSION,
        "COMPANY_NAME": settings.COMPANY_NAME,
        "COMPANY_SUPPORT_EMAIL": settings.COMPANY_SUPPORT_EMAIL,
        "COMPANY_SUPPORT_URL": settings.COMPANY_SUPPORT_URL,
    }
