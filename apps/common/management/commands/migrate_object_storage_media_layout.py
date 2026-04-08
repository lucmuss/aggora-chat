from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.common.image_variants import ensure_optimized_images
from apps.common.upload_paths import build_hashed_upload_path, is_hashed_upload_path
from apps.communities.models import Community
from apps.posts.models import Post


def _read_object_bytes(storage, source_name: str) -> bytes:
    with storage.open(source_name, "rb") as source_handle:
        return source_handle.read()


def _save_object(storage, target_name: str, payload: bytes, *, overwrite: bool = False) -> None:
    if overwrite and storage.exists(target_name):
        storage.delete(target_name)
    storage.save(target_name, ContentFile(payload, name=Path(target_name).name))


def _target_original_name(source_name: str, payload: bytes) -> str:
    normalized_name = source_name.lstrip("/").replace("\\", "/")
    namespace_map = {
        "avatars": "original/avatars",
        "profile_banners": "original/profile_banners",
        "community_icons": "original/community_icons",
        "community_banners": "original/community_banners",
        "post_images": "original/post_images",
    }
    parts = Path(normalized_name).parts
    if not parts:
        return normalized_name
    if parts[0] == "original" and is_hashed_upload_path(normalized_name, root_prefix="original"):
        return normalized_name
    namespace = parts[1] if parts[0] == "original" and len(parts) > 1 else parts[0]
    folder = namespace_map.get(namespace)
    if not folder:
        return normalized_name
    filename = Path(normalized_name).name
    return build_hashed_upload_path(
        folder,
        filename,
        seed=payload,
    )


class Command(BaseCommand):
    help = "Move legacy object-storage image keys into the original/... layout and update DB references."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show planned moves without writing anything.")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace destination objects when the new original/... key already exists.",
        )
        parser.add_argument(
            "--delete-legacy",
            action="store_true",
            help="Delete the old object after the DB reference has been moved.",
        )
        parser.add_argument(
            "--skip-variants",
            action="store_true",
            help="Only move original objects and update DB references, without generating optimized variants.",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "USE_S3", False):
            raise CommandError("USE_S3 must be enabled before migrating object-storage media layout.")

        dry_run = options["dry_run"]
        overwrite = options["overwrite"]
        delete_legacy = options["delete_legacy"]
        skip_variants = options["skip_variants"]

        total = 0
        moved = 0
        updated = 0
        already_aligned = 0
        missing = 0
        deleted = 0
        variant_created = 0
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
                current_name = str(getattr(field_file, "name", "") or "").strip()
                if not current_name:
                    continue

                total += 1
                descriptor = f"{instance._meta.label_lower}:{instance.pk}:{field_name}"
                if not default_storage.exists(current_name):
                    missing += 1
                    self.stdout.write(f"MISSING {descriptor} -> {current_name}")
                    continue

                payload = _read_object_bytes(default_storage, current_name)
                target_name = _target_original_name(current_name, payload)

                if current_name == target_name:
                    self.stdout.write(f"KEEP {descriptor} -> {current_name}")
                    if dry_run or skip_variants:
                        already_aligned += 1
                        continue
                    try:
                        variant_created += len(ensure_optimized_images(field_file, force=overwrite))
                        already_aligned += 1
                    except Exception as exc:  # pragma: no cover
                        errors += 1
                        self.stderr.write(f"ERROR {descriptor} variants for {current_name}: {exc}")
                    continue

                destination_exists = default_storage.exists(target_name)
                action = "MOVE" if not dry_run else "DRY RUN"
                self.stdout.write(f"{action} {descriptor} -> {current_name} => {target_name}")

                if dry_run:
                    continue

                try:
                    if not destination_exists or overwrite:
                        _save_object(default_storage, target_name, payload, overwrite=overwrite)
                        moved += 1

                    instance.__class__._default_manager.filter(pk=instance.pk).update(**{field_name: target_name})
                    setattr(instance, field_name, target_name)
                    updated += 1

                    if not skip_variants:
                        variant_created += len(ensure_optimized_images(getattr(instance, field_name), force=overwrite))

                    if delete_legacy and current_name != target_name and default_storage.exists(current_name):
                        default_storage.delete(current_name)
                        deleted += 1
                except Exception as exc:  # pragma: no cover
                    errors += 1
                    self.stderr.write(f"ERROR {descriptor} -> {current_name} => {target_name}: {exc}")

        self.stdout.write("")
        self.stdout.write(f"Total referenced images: {total}")
        self.stdout.write(f"Moved objects: {moved}")
        self.stdout.write(f"Updated DB references: {updated}")
        self.stdout.write(f"Already aligned: {already_aligned}")
        self.stdout.write(f"Missing source objects: {missing}")
        self.stdout.write(f"Deleted legacy objects: {deleted}")
        self.stdout.write(f"Optimized variants created: {variant_created}")
        self.stdout.write(f"Errors: {errors}")
