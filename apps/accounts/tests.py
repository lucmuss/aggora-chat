from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.communities.models import Community
from apps.posts.models import Comment, Post
from apps.votes.models import SavedPost


User = get_user_model()


class HandleSetupTests(TestCase):
    def test_home_page_renders(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agora starts with communities")

    def test_authenticated_user_without_handle_is_redirected(self):
        user = User.objects.create_user(
            username="handleless",
            email="handleless@example.com",
            password="password123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertRedirects(response, reverse("handle_setup"))

    def test_handle_setup_saves_lowercase_handle(self):
        user = User.objects.create_user(
            username="handleuser",
            email="handleuser@example.com",
            password="password123",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("handle_setup"),
            {"handle": "Agora_User", "display_name": "Agora User"},
        )

        user.refresh_from_db()
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(user.handle, "agora_user")

    def test_profile_saved_tab_renders(self):
        user = User.objects.create_user(
            username="profileuser",
            email="profileuser@example.com",
            password="password123",
            handle="profileuser",
        )
        community = Community.objects.create(
            name="Agora Profiles",
            slug="agora-profiles",
            title="Agora Profiles",
            description="Profile tests.",
            creator=user,
        )
        post = Post.objects.create(
            community=community,
            author=user,
            post_type="text",
            title="Saved thread",
            body_md="Saved",
        )
        SavedPost.objects.create(user=user, post=post)
        Comment.objects.create(post=post, author=user, body_md="Comment", body_html="<p>Comment</p>")

        response = self.client.get(reverse("profile", kwargs={"handle": user.handle}), {"tab": "saved"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saved thread")

    def test_follow_and_block_toggles_work(self):
        user = User.objects.create_user(
            username="viewer",
            email="viewer@example.com",
            password="password123",
            handle="viewer",
        )
        other = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="password123",
            handle="other",
        )
        self.client.force_login(user)

        follow_response = self.client.post(reverse("toggle_follow", kwargs={"handle": other.handle}))
        user.refresh_from_db()
        self.assertRedirects(follow_response, reverse("profile", kwargs={"handle": other.handle}))
        self.assertTrue(user.followed_users.filter(pk=other.pk).exists())

        block_response = self.client.post(reverse("toggle_block", kwargs={"handle": other.handle}))
        user.refresh_from_db()
        self.assertRedirects(block_response, reverse("profile", kwargs={"handle": other.handle}))
        self.assertTrue(user.blocked_users.filter(pk=other.pk).exists())
        self.assertFalse(user.followed_users.filter(pk=other.pk).exists())

    def test_healthz_endpoint_returns_ok(self):
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


class AccountBootstrapCommandTests(TestCase):
    def test_create_test_user_command_uses_env_configuration(self):
        with self.settings(
            TEST_USER_EMAIL="test@freya.app",
            TEST_USER_PASSWORD="TestPass123!",
            TEST_USER_PHONE="+491500000002",
        ):
            call_command("create_test_user")

        user = User.objects.get(email="test@freya.app")
        self.assertEqual(user.handle, "freya_test_user")
        self.assertTrue(user.check_password("TestPass123!"))

    def test_sync_staff_accounts_command_creates_admin_and_moderator(self):
        with self.settings():
            import os

            os.environ["OPS_ADMIN_EMAIL"] = "ops-admin@example.com"
            os.environ["OPS_ADMIN_PASSWORD"] = "StrongPass123!"
            os.environ["OPS_MODERATOR_EMAIL"] = "ops-mod@example.com"
            os.environ["OPS_MODERATOR_PASSWORD"] = "StrongPass123!"
            try:
                call_command("sync_staff_accounts")
            finally:
                os.environ.pop("OPS_ADMIN_EMAIL", None)
                os.environ.pop("OPS_ADMIN_PASSWORD", None)
                os.environ.pop("OPS_MODERATOR_EMAIL", None)
                os.environ.pop("OPS_MODERATOR_PASSWORD", None)

        admin_user = User.objects.get(email="ops-admin@example.com")
        moderator_user = User.objects.get(email="ops-mod@example.com")
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(moderator_user.is_staff)
        self.assertFalse(moderator_user.is_superuser)

    def test_seed_command_imports_freya_seed_users(self):
        call_command("seed", "--skip-demo-content")

        self.assertTrue(User.objects.filter(email="ariane.keller01@mailseed.test").exists())
        self.assertTrue(Community.objects.filter(slug="freya-seed-lounge").exists())
