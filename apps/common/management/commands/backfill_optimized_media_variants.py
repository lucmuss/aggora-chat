from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.common.image_variants import ensure_optimized_images
from apps.communities.models import Community
from apps.posts.models import Post


class Command(BaseCommand):
    help = "Generate optimized WebP media variants for existing image fields."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which image fields would get optimized variants without writing files.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate optimized variants even when they already exist.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        created = 0
        skipped = 0
        errors = 0

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
                descriptor = f"{instance._meta.label_lower}:{instance.pk}:{field_name}"
                if not field_file or not getattr(field_file, "name", ""):
                    skipped += 1
                    continue
                if dry_run:
                    self.stdout.write(f"DRY RUN {descriptor} -> {field_file.name}")
                    created += 1
                    continue
                try:
                    result = ensure_optimized_images(field_file, force=force)
                except Exception as exc:  # pragma: no cover - defensive logging for storage issues
                    errors += 1
                    self.stderr.write(f"ERROR {descriptor}: {exc}")
                    continue
                if result:
                    created += len(result)
                else:
                    skipped += 1

        self.stdout.write(f"Optimized variants created: {created}")
        self.stdout.write(f"Skipped: {skipped}")
        self.stdout.write(f"Errors: {errors}")
