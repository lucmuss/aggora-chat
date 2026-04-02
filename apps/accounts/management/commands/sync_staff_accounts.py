from __future__ import annotations

from django.core.management.base import BaseCommand

from config.env import env_str

from apps.communities.models import Community, CommunityMembership
from apps.accounts.seed_utils import ensure_account


class Command(BaseCommand):
    help = "Create or update operations admin and moderator accounts from environment variables."

    def handle(self, *args, **options):
        processed = 0
        definitions = [
            (
                "admin",
                env_str("OPS_ADMIN_EMAIL", "").strip().lower(),
                env_str("OPS_ADMIN_PASSWORD", "").strip(),
                env_str("OPS_ADMIN_PHONE", "").strip(),
                True,
                True,
                "ops_admin",
                "Operations Admin",
            ),
            (
                "moderator",
                env_str("OPS_MODERATOR_EMAIL", "").strip().lower(),
                env_str("OPS_MODERATOR_PASSWORD", "").strip(),
                env_str("OPS_MODERATOR_PHONE", "").strip(),
                True,
                False,
                "ops_moderator",
                "Operations Moderator",
            ),
        ]

        for role, email, password, phone, is_staff, is_superuser, handle, display_name in definitions:
            if not email or not password:
                self.stdout.write(self.style.WARNING(f"skip {role}: email/password not configured"))
                continue

            user, created = ensure_account(
                email=email,
                password=password,
                handle=handle,
                display_name=display_name,
                bio=f"Bootstrap {role} account for Agora operations. Phone reference: {phone or 'n/a'}.",
                is_staff=is_staff,
                is_superuser=is_superuser,
            )
            seed_community = Community.objects.filter(slug="freya-seed-lounge").first()
            if seed_community and role == "moderator":
                CommunityMembership.objects.update_or_create(
                    user=user,
                    community=seed_community,
                    defaults={"role": CommunityMembership.Role.MODERATOR},
                )
            processed += 1
            self.stdout.write(self.style.SUCCESS(f"{'created' if created else 'updated'} {role}: {user.email}"))

        self.stdout.write(self.style.SUCCESS(f"staff accounts processed: {processed}"))
