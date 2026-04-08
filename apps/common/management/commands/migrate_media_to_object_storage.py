from __future__ import annotations

from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db.models import FileField


class Command(BaseCommand):
    help = "Copy existing files from the local media directory into the configured default storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be copied without writing anything.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace objects that already exist in the destination storage.",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "USE_S3", False):
            raise CommandError("USE_S3 must be enabled before migrating media to object storage.")

        source_root = Path(getattr(settings, "LOCAL_MEDIA_ROOT", settings.BASE_DIR / "media"))
        if not source_root.exists():
            raise CommandError(f"Local media directory does not exist: {source_root}")

        source_storage = FileSystemStorage(location=source_root)
        dry_run = options["dry_run"]
        overwrite = options["overwrite"]

        total = 0
        copied = 0
        skipped = 0
        missing = 0
        errors = 0

        for model in apps.get_models():
            file_fields = [
                field
                for field in model._meta.get_fields()
                if isinstance(field, FileField) and not getattr(field, "auto_created", False)
            ]
            if not file_fields:
                continue

            queryset = model._default_manager.all().only("pk", *[field.name for field in file_fields])
            for instance in queryset.iterator():
                for field in file_fields:
                    field_file = getattr(instance, field.name)
                    file_name = str(field_file.name or "").strip()
                    if not file_name:
                        continue

                    total += 1

                    if not source_storage.exists(file_name):
                        missing += 1
                        self.stdout.write(f"MISSING {model._meta.label}#{instance.pk} {field.name} -> {file_name}")
                        continue

                    destination_exists = default_storage.exists(file_name)
                    if destination_exists and not overwrite:
                        skipped += 1
                        self.stdout.write(f"SKIP {model._meta.label}#{instance.pk} {field.name} -> {file_name}")
                        continue

                    action = "COPY" if not dry_run else "DRY-RUN"
                    self.stdout.write(f"{action} {model._meta.label}#{instance.pk} {field.name} -> {file_name}")

                    if dry_run:
                        continue

                    try:
                        if destination_exists and overwrite:
                            default_storage.delete(file_name)
                        with source_storage.open(file_name, "rb") as source_handle:
                            default_storage.save(file_name, source_handle)
                        copied += 1
                    except Exception as exc:
                        errors += 1
                        self.stderr.write(
                            f"ERROR {model._meta.label}#{instance.pk} {field.name} -> {file_name}: {exc}"
                        )

        self.stdout.write("")
        self.stdout.write(f"Total referenced files: {total}")
        self.stdout.write(f"Copied: {copied}")
        self.stdout.write(f"Skipped existing: {skipped}")
        self.stdout.write(f"Missing locally: {missing}")
        self.stdout.write(f"Errors: {errors}")
