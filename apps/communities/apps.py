from django.apps import AppConfig


class CommunitiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.communities"
    label = "communities"
    verbose_name = "Communities"

    def ready(self):
        from . import signals  # noqa: F401
