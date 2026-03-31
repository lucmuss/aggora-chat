from apps.common.celery import dispatch_task
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.search.tasks import index_post_task

from .models import Post


@receiver(post_save, sender=Post)
def queue_index_post(sender, instance, **kwargs):
    dispatch_task(index_post_task, instance.pk)
