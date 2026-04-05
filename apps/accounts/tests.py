import time

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.communities.models import Community, CommunityChallenge
from apps.posts.models import Comment, Post
from apps.posts.services import submit_comment, submit_post
from apps.votes.models import SavedPost, Vote

from .models import Notification, UserBadge
from .security import _totp_at, generate_totp_secret

User = get_user_model()


class HandleSetupTests(TestCase):
    def test_home_page_renders(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome to Agora")

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
        self.assertRedirects(response, reverse("start_with_friends"))
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

    def test_start_with_friends_completes_onboarding_and_redirects_to_post_create(self):
        user = User.objects.create_user(
            username="newbie",
            email="newbie@example.com",
            password="password123",
            handle="newbie",
        )
        community = Community.objects.create(
            name="Agora Onboarding",
            slug="agora-onboarding",
            title="Agora Onboarding",
            description="Start here.",
            creator=user,
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("start_with_friends"),
            {
                "display_name": "New Builder",
                "bio": "Ready to join communities.",
                "communities": [community.pk],
                "first_post_community": community.pk,
                "first_contribution_type": "post",
            },
        )

        user.refresh_from_db()
        self.assertTrue(user.onboarding_completed)
        self.assertEqual(user.display_name, "New Builder")
        self.assertEqual(user.bio, "Ready to join communities.")
        self.assertTrue(UserBadge.objects.filter(user=user, code=UserBadge.BadgeCode.FIRST_STEPS).exists())
        self.assertTrue(UserBadge.objects.filter(user=user, code=UserBadge.BadgeCode.PROFILE_READY).exists())
        self.assertRedirects(response, reverse("create_post", kwargs={"community_slug": community.slug}))

    def test_start_with_friends_can_redirect_to_comment_on_existing_thread(self):
        user = User.objects.create_user(
            username="commentstarter",
            email="commentstarter@example.com",
            password="password123",
            handle="commentstarter",
        )
        community = Community.objects.create(
            name="Agora Replies",
            slug="agora-replies",
            title="Agora Replies",
            description="Reply here.",
            creator=user,
        )
        post = Post.objects.create(
            community=community,
            author=user,
            post_type="text",
            title="Starter thread",
            body_md="Kick things off.",
            comment_count=2,
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("start_with_friends"),
            {
                "communities": [community.pk],
                "first_post_community": community.pk,
                "first_contribution_type": "comment",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('post_detail', kwargs={'community_slug': community.slug, 'post_id': post.id, 'slug': post.slug})}?reply=1&welcome=1",
            fetch_redirect_response=False,
        )

    def test_profile_comments_tab_shows_comment_vote_state(self):
        viewer = User.objects.create_user(
            username="commentviewer",
            email="commentviewer@example.com",
            password="password123",
            handle="commentviewer",
        )
        author = User.objects.create_user(
            username="commentauthor",
            email="commentauthor@example.com",
            password="password123",
            handle="commentauthor",
        )
        community = Community.objects.create(
            name="Agora Comment Profiles",
            slug="agora-comment-profiles",
            title="Agora Comment Profiles",
            description="Comment profile tests.",
            creator=author,
        )
        post = Post.objects.create(
            community=community,
            author=author,
            post_type="text",
            title="Comment target",
            body_md="Body",
        )
        comment = Comment.objects.create(post=post, author=author, body_md="Profile comment", body_html="<p>Profile comment</p>")
        Vote.objects.create(user=viewer, comment=comment, value=Vote.VoteType.UPVOTE)
        self.client.force_login(viewer)

        response = self.client.get(reverse("profile", kwargs={"handle": author.handle}), {"tab": "comments"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile comment")
        self.assertContains(
            response,
            reverse(
                "post_detail",
                kwargs={"community_slug": community.slug, "post_id": post.id, "slug": post.slug},
            ),
        )

    def test_notifications_page_marks_reply_notifications_as_read(self):
        author = User.objects.create_user(
            username="author",
            email="author@example.com",
            password="password123",
            handle="author",
        )
        replier = User.objects.create_user(
            username="replier",
            email="replier@example.com",
            password="password123",
            handle="replier",
        )
        community = Community.objects.create(
            name="Agora Notifications",
            slug="agora-notifications",
            title="Agora Notifications",
            description="Notification tests.",
            creator=author,
        )
        post = Post.objects.create(
            community=community,
            author=author,
            post_type="text",
            title="Notify me",
            body_md="Body",
        )
        submit_comment(replier, post, "Reply body")
        self.client.force_login(author)

        response = self.client.get(reverse("notifications"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "replied to your post")
        self.assertFalse(Notification.objects.filter(user=author, is_read=False).exists())

    @override_settings(
        SOCIALACCOUNT_PROVIDERS={
            "google": {"APP": {"client_id": "", "secret": ""}},
            "github": {"APP": {"client_id": "github-client", "secret": "github-secret"}},
            "openid_connect": {"APPS": []},
        }
    )
    def test_signup_page_can_surface_github_call_to_action(self):
        response = self.client.get(reverse("account_signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Continue with GitHub")

    def test_login_page_links_to_reset_password_flow(self):
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forgot Password?")

    def test_authenticated_user_can_view_custom_account_management_pages(self):
        user = User.objects.create_user(
            username="accountflow",
            email="accountflow@example.com",
            password="password123",
            handle="accountflow",
        )
        self.client.force_login(user)

        settings_response = self.client.get(reverse("account_settings"))
        email_response = self.client.get(reverse("account_email"))
        password_response = self.client.get(reverse("account_change_password"))
        connections_response = self.client.get(reverse("socialaccount_connections"))

        self.assertEqual(settings_response.status_code, 200)
        self.assertContains(settings_response, "Manage email addresses")
        self.assertContains(settings_response, "Connected accounts")
        self.assertEqual(email_response.status_code, 200)
        self.assertContains(email_response, "Email Addresses")
        self.assertEqual(password_response.status_code, 200)
        self.assertContains(password_response, "Change Password")
        self.assertEqual(connections_response.status_code, 200)
        self.assertContains(connections_response, "Third-party sign-in")

    def test_referral_hub_renders_for_joined_communities(self):
        user = User.objects.create_user(
            username="grower",
            email="grower@example.com",
            password="password123",
            handle="grower",
        )
        community = Community.objects.create(
            name="Agora Growth",
            slug="agora-growth",
            title="Agora Growth",
            description="Growth tests.",
            creator=user,
        )
        community.memberships.create(user=user, role=community.memberships.model.Role.MEMBER)
        self.client.force_login(user)

        response = self.client.get(reverse("account_referrals"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Referral links and activation badges")
        self.assertContains(response, "c/agora-growth")

    def test_first_post_and_comment_badges_are_awarded(self):
        user = User.objects.create_user(
            username="badges",
            email="badges@example.com",
            password="password123",
            handle="badges",
        )
        community = Community.objects.create(
            name="Agora Badges",
            slug="agora-badges",
            title="Agora Badges",
            description="Badge tests.",
            creator=user,
        )

        post = submit_post(
            user=user,
            community=community,
            post_data={
                "title": "Existing post",
                "body_md": "Body",
                "post_type": "text",
            },
        )
        submit_comment(user, post, "First comment")

        self.assertTrue(UserBadge.objects.filter(user=user, code=UserBadge.BadgeCode.FIRST_POST).exists())
        self.assertTrue(UserBadge.objects.filter(user=user, code=UserBadge.BadgeCode.FIRST_COMMENT).exists())

    def test_joining_a_challenge_awards_engagement_badges(self):
        user = User.objects.create_user(
            username="challenger",
            email="challenger@example.com",
            password="password123",
            handle="challenger",
        )
        community = Community.objects.create(
            name="Agora Challenges",
            slug="agora-challenges",
            title="Agora Challenges",
            description="Challenge tests.",
            creator=user,
        )
        challenge = CommunityChallenge.objects.create(
            community=community,
            created_by=user,
            title="Ship it week",
            prompt_md="Share one thing you shipped.",
            starts_at=timezone.now() - timezone.timedelta(days=1),
            ends_at=timezone.now() + timezone.timedelta(days=3),
        )
        community.memberships.create(user=user, role=community.memberships.model.Role.MEMBER)
        self.client.force_login(user)

        response = self.client.post(
            reverse("community_challenge_join", kwargs={"slug": community.slug, "challenge_id": challenge.id})
        )

        self.assertRedirects(response, reverse("community_detail", kwargs={"slug": community.slug}))
        self.assertTrue(UserBadge.objects.filter(user=user, code=UserBadge.BadgeCode.CHALLENGE_ACCEPTED).exists())

    def test_account_settings_updates_privacy_and_notification_preferences(self):
        user = User.objects.create_user(
            username="settingsuser",
            email="settingsuser@example.com",
            password="password123",
            handle="settingsuser",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("account_settings"),
            {
                "display_name": "Settings User",
                "bio": "Testing profile settings.",
                "profile_visibility": User.ProfileVisibility.MEMBERS,
                "email_notifications_enabled": "on",
                "notify_on_replies": "on",
            },
        )

        user.refresh_from_db()
        self.assertRedirects(response, reverse("account_settings"))
        self.assertEqual(user.display_name, "Settings User")
        self.assertEqual(user.profile_visibility, User.ProfileVisibility.MEMBERS)
        self.assertTrue(user.email_notifications_enabled)

    def test_staff_user_is_redirected_to_mfa_setup_for_sensitive_routes(self):
        user = User.objects.create_user(
            username="staffer",
            email="staffer@example.com",
            password="password123",
            handle="staffer",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get("/admin/")

        self.assertRedirects(response, reverse("account_mfa_setup"))

    def test_mfa_setup_enables_totp_for_staff(self):
        user = User.objects.create_user(
            username="mfastaff",
            email="mfastaff@example.com",
            password="password123",
            handle="mfastaff",
            is_staff=True,
        )
        user.mfa_totp_secret = generate_totp_secret()
        user.save(update_fields=["mfa_totp_secret"])
        self.client.force_login(user)
        current_code = _totp_at(user.mfa_totp_secret, int(time.time()) // 30)

        response = self.client.post(reverse("account_mfa_setup"), {"code": current_code})

        user.refresh_from_db()
        self.assertRedirects(response, reverse("account_settings"))
        self.assertTrue(user.mfa_totp_enabled)

    def test_reply_notifications_respect_user_preferences(self):
        author = User.objects.create_user(
            username="quietauthor",
            email="quietauthor@example.com",
            password="password123",
            handle="quietauthor",
            notify_on_replies=False,
        )
        replier = User.objects.create_user(
            username="quietreplier",
            email="quietreplier@example.com",
            password="password123",
            handle="quietreplier",
        )
        community = Community.objects.create(
            name="Agora Quiet",
            slug="agora-quiet",
            title="Agora Quiet",
            description="Preference tests.",
            creator=author,
        )
        post = Post.objects.create(
            community=community,
            author=author,
            post_type="text",
            title="No alerts please",
            body_md="Body",
        )

        submit_comment(replier, post, "Reply body")

        self.assertFalse(Notification.objects.filter(user=author).exists())


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

    def test_seed_command_imports_demo_users_and_admins(self):
        call_command("seed", "--skip-demo-content")

        self.assertTrue(User.objects.filter(email="ariane.keller01@mailseed.test").exists())
        self.assertTrue(User.objects.filter(email="ops-admin@aggora.app", is_superuser=True).exists())
        self.assertTrue(User.objects.filter(email="ops-moderator@aggora.app", is_staff=True).exists())
        self.assertTrue(Community.objects.filter(slug="freya-seed-lounge").exists())
        self.assertTrue(Community.objects.filter(slug="product-design").exists())
        self.assertTrue(Community.objects.filter(slug="slow-tech-club").exists())
