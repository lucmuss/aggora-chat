from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.common.celery import dispatch_task
from apps.common.image_variants import delete_optimized_image
from apps.common.tasks import generate_media_variants_task

from .models import Community


@receiver(pre_save, sender=Community)
def cleanup_replaced_community_image_variants(sender, instance, **kwargs):
    if not instance.pk:
        return
    previous = sender.objects.filter(pk=instance.pk).only("icon", "banner").first()
    if previous is None:
        return
    if previous.icon and previous.icon.name != getattr(instance.icon, "name", ""):
        delete_optimized_image(previous.icon)
    if previous.banner and previous.banner.name != getattr(instance.banner, "name", ""):
        delete_optimized_image(previous.banner)


@receiver(post_save, sender=Community)
def ensure_community_image_variants(sender, instance, **kwargs):
    transaction.on_commit(
        lambda: dispatch_task(
            generate_media_variants_task,
            instance._meta.label_lower,
            instance.pk,
            ["icon", "banner"],
        )
    )


@receiver(post_delete, sender=Community)
def cleanup_deleted_community_image_variants(sender, instance, **kwargs):
    delete_optimized_image(instance.icon)
    delete_optimized_image(instance.banner)
