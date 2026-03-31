from django.conf import settings


def dispatch_task(task, *args, **kwargs):
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return task(*args, **kwargs)
    return task.delay(*args, **kwargs)
