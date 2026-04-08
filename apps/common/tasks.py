from __future__ import annotations

from celery import shared_task
from django.apps import apps

from apps.common.image_variants import ensure_optimized_images


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def generate_media_variants_task(self, model_label: str, object_id: int, field_names: list[str], force: bool = False):
    model = apps.get_model(model_label)
    if model is None:
        return []

    instance = model.objects.filter(pk=object_id).first()
    if instance is None:
        return []

    created: list[str] = []
    for field_name in field_names:
        field_file = getattr(instance, field_name, None)
        created.extend(ensure_optimized_images(field_file, force=force))
    return created
