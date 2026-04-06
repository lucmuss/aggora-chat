from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.communities.models import Community, CommunityMembership
from apps.posts.models import Post

from .models import Ban, ModAction, ModQueueItem, RemovalReason, Report

User = get_user_model()


class ModerationFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="password123",
            handle="owner",
        )
        self.member = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="password123",
            handle="member",
        )
        self.reporter = User.objects.create_user(
            username="reporter",
            email="reporter@example.com",
            password="password123",
            handle="reporter",
        )
        self.community = Community.objects.create(
            name="Agora Moderation",
            slug="agora-moderation",
            title="Agora Moderation",
            description="Moderation tests.",
            creator=self.owner,
        )
        self.owner.mfa_totp_enabled = True
        self.owner.save(update_fields=["mfa_totp_enabled"])
        CommunityMembership.objects.create(
            user=self.owner,
            community=self.community,
            role=CommunityMembership.Role.OWNER,
        )
        CommunityMembership.objects.create(
            user=self.member,
            community=self.community,
            role=CommunityMembership.Role.MEMBER,
        )
        self.post = Post.objects.create(
            community=self.community,
            author=self.member,
            post_type="text",
            title="Flag me",
            body_md="Needs review",
        )
        self.removal_reason = RemovalReason.objects.create(
            community=self.community,
            code="spam",
            title="Spam",
            message_md="Removed as spam",
        )

    def test_report_creates_queue_item(self):
        self.client.force_login(self.reporter)

        response = self.client.post(
            reverse("report_content"),
            {"post_id": self.post.id, "reason": "spam", "details": "Looks suspicious"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(ModQueueItem.objects.count(), 1)
        self.assertEqual(ModQueueItem.objects.first().status, ModQueueItem.Status.REPORTED)

    def test_report_rejects_self_reports(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("report_content"),
            {"post_id": self.post.id, "reason": "spam", "details": "Self report"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You cannot report your own content.")
        self.assertEqual(Report.objects.count(), 0)

    def test_owner_can_remove_post_and_log_action(self):
        queue_item = ModQueueItem.objects.create(
            community=self.community,
            post=self.post,
            content_type=ModQueueItem.ContentType.POST,
            status=ModQueueItem.Status.NEEDS_REVIEW,
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("mod_action", kwargs={"community_slug": self.community.slug}),
            {
                "post_id": self.post.id,
                "action_type": "remove_post",
                "reason_code": self.removal_reason.code,
                "reason_text": "Confirmed spam",
            },
        )

        self.post.refresh_from_db()
        queue_item.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.post.is_removed)
        self.assertEqual(queue_item.status, ModQueueItem.Status.REMOVED)
        self.assertEqual(ModAction.objects.filter(action_type="remove_post").count(), 1)

    def test_owner_can_lock_and_unlock_post(self):
        self.client.force_login(self.owner)

        lock_response = self.client.post(
            reverse("mod_action", kwargs={"community_slug": self.community.slug}),
            {
                "post_id": self.post.id,
                "action_type": "lock_post",
                "reason_text": "Pause thread",
            },
        )
        self.post.refresh_from_db()
        self.assertEqual(lock_response.status_code, 302)
        self.assertTrue(self.post.is_locked)

        unlock_response = self.client.post(
            reverse("mod_action", kwargs={"community_slug": self.community.slug}),
            {
                "post_id": self.post.id,
                "action_type": "unlock_post",
                "reason_text": "Reopen thread",
            },
        )
        self.post.refresh_from_db()
        self.assertEqual(unlock_response.status_code, 302)
        self.assertFalse(self.post.is_locked)

    def test_owner_can_sticky_and_unsticky_post(self):
        self.client.force_login(self.owner)

        sticky_response = self.client.post(
            reverse("mod_action", kwargs={"community_slug": self.community.slug}),
            {
                "post_id": self.post.id,
                "action_type": "sticky_post",
                "reason_text": "Highlight thread",
            },
        )
        self.post.refresh_from_db()
        self.assertEqual(sticky_response.status_code, 302)
        self.assertTrue(self.post.is_stickied)

        unsticky_response = self.client.post(
            reverse("mod_action", kwargs={"community_slug": self.community.slug}),
            {
                "post_id": self.post.id,
                "action_type": "unsticky_post",
                "reason_text": "Normal ranking again",
            },
        )
        self.post.refresh_from_db()
        self.assertEqual(unsticky_response.status_code, 302)
        self.assertFalse(self.post.is_stickied)

    def test_banned_user_cannot_create_post(self):
        Ban.objects.create(
            community=self.community,
            user=self.member,
            banned_by=self.owner,
            is_permanent=True,
            reason="Bad faith posting",
        )
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("create_post", kwargs={"community_slug": self.community.slug}),
            {"post_type": "text", "title": "Blocked", "body_md": "This should fail"},
        )

        self.assertEqual(response.status_code, 403)

    def test_owner_can_view_mod_queue_and_log(self):
        ModQueueItem.objects.create(
            community=self.community,
            post=self.post,
            content_type=ModQueueItem.ContentType.POST,
            status=ModQueueItem.Status.NEEDS_REVIEW,
        )
        Report.objects.create(
            reporter=self.reporter,
            post=self.post,
            reason="spam",
            details="Please remove this.",
            queue_item=ModQueueItem.objects.first(),
        )
        ModAction.objects.create(
            community=self.community,
            moderator=self.owner,
            action_type=ModAction.ActionType.APPROVE_POST,
            target_post=self.post,
        )
        self.client.force_login(self.owner)

        queue_response = self.client.get(reverse("mod_queue", kwargs={"community_slug": self.community.slug}))
        log_response = self.client.get(reverse("mod_log", kwargs={"community_slug": self.community.slug}))

        self.assertEqual(queue_response.status_code, 200)
        self.assertEqual(log_response.status_code, 200)
        self.assertContains(queue_response, "Mod queue")
        self.assertContains(queue_response, "Please remove this.")
        self.assertContains(log_response, "Moderation log")

    def test_mod_mail_thread_can_be_created_and_replied_to(self):
        self.client.force_login(self.reporter)

        create_response = self.client.post(
            reverse("mod_mail_create", kwargs={"community_slug": self.community.slug}),
            {"subject": "Appeal", "body_md": "Please review this action"},
        )

        self.assertEqual(create_response.status_code, 302)
        thread_id = int(create_response.url.rstrip("/").split("/")[-1])
        self.client.force_login(self.owner)
        reply_response = self.client.post(
            reverse("mod_mail_thread", kwargs={"community_slug": self.community.slug, "thread_id": thread_id}),
            {"body_md": "We are reviewing it."},
        )

        self.assertEqual(reply_response.status_code, 302)
        thread_view = self.client.get(
            reverse("mod_mail_thread", kwargs={"community_slug": self.community.slug, "thread_id": thread_id})
        )
        self.assertContains(thread_view, "We are reviewing it.")
