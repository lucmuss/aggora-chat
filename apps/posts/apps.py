from django.apps import AppConfig


class PostsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.posts"
    label = "posts"
    verbose_name = "Posts"

    def ready(self):
        from . import signals  # noqa: F401
