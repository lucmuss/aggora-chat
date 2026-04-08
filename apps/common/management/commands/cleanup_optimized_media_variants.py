from __future__ import annotations

from pathlib import Path

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.common.image_variants import OPTIMIZED_IMAGE_PREFIX, iter_variant_names
from apps.communities.models import Community
from apps.posts.models import Post


def _iter_storage_variant_names(storage):
    if hasattr(storage, "bucket"):
        yield from (obj.key for obj in storage.bucket.objects.filter(Prefix=f"{OPTIMIZED_IMAGE_PREFIX}/"))
        return

    location = getattr(storage, "location", "")
    if not location:
        return
    variant_root = Path(location) / OPTIMIZED_IMAGE_PREFIX
    if not variant_root.exists():
        return
    for path in variant_root.rglob("*"):
        if path.is_file():
            yield str(path.relative_to(location)).replace("\\", "/")


class Command(BaseCommand):
    help = "Delete optimized image variants that no longer correspond to a referenced source image."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which optimized variants would be deleted without removing files.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        expected = set()

        targets = [
            (User.objects.exclude(avatar=""), "avatar"),
            (User.objects.exclude(banner=""), "banner"),
            (Community.objects.exclude(icon=""), "icon"),
            (Community.objects.exclude(banner=""), "banner"),
            (Post.objects.exclude(image=""), "image"),
        ]
        for queryset, field_name in targets:
            for instance in queryset.iterator():
                field_file = getattr(instance, field_name)
                if field_file and getattr(field_file, "name", ""):
                    expected.update(iter_variant_names(field_file.name))

        actual = set(_iter_storage_variant_names(default_storage))
        orphaned = sorted(actual - expected)

        for name in orphaned:
            if dry_run:
                self.stdout.write(f"DRY RUN delete {name}")
                continue
            default_storage.delete(name)
            self.stdout.write(f"Deleted {name}")

        self.stdout.write(f"Expected optimized variants: {len(expected)}")
        self.stdout.write(f"Orphaned optimized variants: {len(orphaned)}")
