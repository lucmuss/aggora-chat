from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.accounts.seed_utils import seed_demo_accounts


class Command(BaseCommand):
    help = "Seed Agora with demo users, admin accounts, memberships, and starter content."

    def add_arguments(self, parser):
        parser.add_argument("--file", dest="file_path", default="", help="Path to a demo users JSON file.")
        parser.add_argument("--admins-file", dest="admins_file_path", default="", help="Path to a demo admins JSON file.")
        parser.add_argument("--communities-file", dest="communities_file_path", default="", help="Path to a demo communities JSON file.")
        parser.add_argument(
            "--skip-demo-content",
            action="store_true",
            help="Only sync users and memberships without creating intro posts/comments.",
        )
        parser.add_argument(
            "--skip-defaults",
            action="store_true",
            help="Accepted for Freya bootstrap compatibility; no-op in Agora.",
        )

    def handle(self, *args, **options):
        summary = seed_demo_accounts(
            users_file_path=options["file_path"] or None,
            admins_file_path=options["admins_file_path"] or None,
            communities_file_path=options["communities_file_path"] or None,
            create_demo_content=not options["skip_demo_content"],
        )
        self.stdout.write(self.style.SUCCESS(f"seed file: {summary['seed_file']}"))
        self.stdout.write(self.style.SUCCESS(f"admins file: {summary['admins_file']}"))
        self.stdout.write(self.style.SUCCESS(f"communities file: {summary['communities_file']}"))
        self.stdout.write(self.style.SUCCESS(f"community: c/{summary['community_slug']}"))
        self.stdout.write(self.style.SUCCESS(f"users created: {summary['users_created']}"))
        self.stdout.write(self.style.SUCCESS(f"admins created: {summary['admins_created']}"))
        self.stdout.write(self.style.SUCCESS(f"communities created: {summary['communities_created']}"))
        self.stdout.write(self.style.SUCCESS(f"posts created: {summary['posts_created']}"))
        self.stdout.write(self.style.SUCCESS(f"comments created: {summary['comments_created']}"))
