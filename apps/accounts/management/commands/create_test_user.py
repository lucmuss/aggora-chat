from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from config.env import env_str

from apps.accounts.seed_utils import ensure_account


class Command(BaseCommand):
    help = "Create or update the bootstrap QA test user."

    def handle(self, *args, **options):
        email = settings.TEST_USER_EMAIL or env_str("TEST_USER_EMAIL", "").strip().lower()
        password = settings.TEST_USER_PASSWORD or env_str("TEST_USER_PASSWORD", "").strip()
        phone = settings.TEST_USER_PHONE or env_str("TEST_USER_PHONE", "").strip()
        if not email or not password:
            raise CommandError("TEST_USER_EMAIL and TEST_USER_PASSWORD must be set.")
        user, created = ensure_account(
            email=email,
            password=password,
            handle="freya_test_user",
            display_name="Freya Test User",
            bio=f"Bootstrap test user imported for Agora QA. Phone reference: {phone}.",
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'created' if created else 'updated'} test user: {user.email} ({settings.APP_NAME})"
            )
        )
