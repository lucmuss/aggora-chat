from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.common.celery import dispatch_task
from apps.common.image_variants import delete_optimized_image
from apps.common.tasks import generate_media_variants_task
from apps.search.tasks import index_post_task

from .models import Post


@receiver(post_save, sender=Post)
def queue_index_post(sender, instance, **kwargs):
    dispatch_task(index_post_task, instance.pk)


@receiver(pre_save, sender=Post)
def cleanup_replaced_post_image_variants(sender, instance, **kwargs):
    if not instance.pk:
        return
    previous = sender.objects.filter(pk=instance.pk).only("image").first()
    if previous and previous.image and previous.image.name != getattr(instance.image, "name", ""):
        delete_optimized_image(previous.image)


@receiver(post_save, sender=Post)
def ensure_post_image_variants(sender, instance, **kwargs):
    transaction.on_commit(
        lambda: dispatch_task(
            generate_media_variants_task,
            instance._meta.label_lower,
            instance.pk,
            ["image"],
        )
    )


@receiver(post_delete, sender=Post)
def cleanup_deleted_post_image_variants(sender, instance, **kwargs):
    delete_optimized_image(instance.image)
