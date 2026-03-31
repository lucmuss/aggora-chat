from celery import shared_task
from django.conf import settings


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def index_post_task(self, post_id):
    if settings.SEARCH_BACKEND != "elasticsearch" or not settings.SEARCH_INDEX_ENABLED:
        return
    try:
        from apps.posts.models import Post
        from .documents import PostDocument

        post = Post.objects.for_listing().get(pk=post_id)
        if PostDocument is not None:
            PostDocument().update(post)
    except Exception as exc:  # pragma: no cover
        if settings.DEBUG:
            return
        raise self.retry(exc=exc)
