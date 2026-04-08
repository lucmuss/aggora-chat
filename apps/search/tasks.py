from celery import shared_task


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def index_post_task(self, post_id):
    # Search indexing used to happen here. The project is now SQL-only, so
    # callers can keep dispatching this task without any side effects.
    return None
