import pytest
from django.contrib.auth import get_user_model
from django.urls import resolve, reverse

from apps.communities.models import Community, CommunityMembership
from apps.moderation.models import Ban, ModAction, ModMail, ModQueueItem, RemovalReason, Report
from apps.moderation.services import (
    create_mod_mail,
    create_mod_mail_reply,
    execute_ban,
    execute_mod_action,
    submit_report,
)
from apps.posts.models import Comment, Post


User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "moderation_view_user"),
        "email": overrides.pop("email", "moderation_view_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "moderation_view_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="moderation-services", creator=None, **overrides):
    creator = creator or make_user(
        username=f"{slug}_creator",
        email=f"{slug}_creator@example.com",
        handle=f"{slug}_creator",
    )
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "Moderation service tests",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestModerationServicesAndViews:
    def setup_method(self):
        self.owner = make_user(username="owner_mod", email="owner_mod@example.com", handle="owner_mod")
        self.owner.mfa_totp_enabled = True
        self.owner.save(update_fields=["mfa_totp_enabled"])
        self.moderator = make_user(username="moderator_mod", email="moderator_mod@example.com", handle="moderator_mod")
        self.reporter = make_user(username="reporter_mod", email="reporter_mod@example.com", handle="reporter_mod")
        self.member = make_user(username="member_mod", email="member_mod@example.com", handle="member_mod")
        self.other = make_user(username="other_mod", email="other_mod@example.com", handle="other_mod")
        self.community = make_community("moderation-services", creator=self.owner)
        CommunityMembership.objects.create(user=self.owner, community=self.community, role=CommunityMembership.Role.OWNER)
        CommunityMembership.objects.create(
            user=self.moderator,
            community=self.community,
            role=CommunityMembership.Role.MODERATOR,
        )
        CommunityMembership.objects.create(user=self.member, community=self.community, role=CommunityMembership.Role.MEMBER)
        self.post = Post.objects.create(
            community=self.community,
            author=self.member,
            post_type=Post.PostType.TEXT,
            title="Moderate me",
            body_md="Needs review",
        )
        self.comment = Comment.objects.create(post=self.post, author=self.member, body_md="Reply", body_html="<p>Reply</p>")
        self.reason = RemovalReason.objects.create(
            community=self.community,
            code="spam",
            title="Spam",
            message_md="Removed as spam",
        )

    def test_execute_mod_action_updates_targets_queue_and_log(self):
        queue_item = ModQueueItem.objects.create(
            community=self.community,
            comment=self.comment,
            content_type=ModQueueItem.ContentType.COMMENT,
            status=ModQueueItem.Status.REPORTED,
        )

        execute_mod_action(
            moderator=self.owner,
            community=self.community,
            action_type=ModAction.ActionType.REMOVE_COMMENT,
            comment_id=str(self.comment.id),
            reason_code="spam",
            reason_text="Confirmed spam",
        )

        self.comment.refresh_from_db()
        queue_item.refresh_from_db()

        assert self.comment.is_removed is True
        assert queue_item.status == ModQueueItem.Status.REMOVED
        assert queue_item.resolved_by == self.owner
        assert ModAction.objects.filter(action_type=ModAction.ActionType.REMOVE_COMMENT).count() == 1

    def test_submit_report_creates_comment_queue_item(self):
        report, community, post, comment = submit_report(
            reporter=self.reporter,
            post_id=None,
            comment_id=str(self.comment.id),
            reason="toxicity",
            details="Escalate this reply",
        )

        assert report.reason == "toxicity"
        assert community == self.community
        assert post is None
        assert comment == self.comment
        assert report.queue_item.content_type == ModQueueItem.ContentType.COMMENT
        assert Report.objects.count() == 1

    def test_execute_ban_supports_timed_and_permanent_bans(self):
        timed = execute_ban(
            moderator=self.owner,
            community=self.community,
            target_user=self.member,
            duration_days=7,
            reason="Cooling off",
        )
        permanent = execute_ban(
            moderator=self.owner,
            community=self.community,
            target_user=self.member,
            duration_days=0,
            reason="Permanent ban",
        )

        assert timed.is_permanent is False
        assert timed.expires_at is not None
        assert permanent.is_permanent is True
        assert permanent.expires_at is None
        assert ModAction.objects.filter(action_type=ModAction.ActionType.BAN_USER).count() == 2

    def test_create_mod_mail_and_reply_render_messages(self):
        thread = create_mod_mail(
            creator=self.reporter,
            community=self.community,
            body_md="**Please review**",
            title="Appeal",
        )
        reply = create_mod_mail_reply(
            author=self.owner,
            thread=thread,
            body_md="We are checking.",
            is_mod_reply=True,
        )

        assert thread.subject == "Appeal"
        assert "<strong>Please review</strong>" in thread.messages.first().body_html
        assert reply.is_mod_reply is True
        assert reply.body_html.startswith("<p>")

    def test_mod_queue_and_log_require_moderation_permissions(self, client):
        client.force_login(self.member)

        queue_response = client.get(reverse("mod_queue", kwargs={"community_slug": self.community.slug}))
        log_response = client.get(reverse("mod_log", kwargs={"community_slug": self.community.slug}))

        assert queue_response.status_code == 403
        assert log_response.status_code == 403

    def test_mod_action_returns_htmx_partial(self, client):
        ModQueueItem.objects.create(
            community=self.community,
            post=self.post,
            content_type=ModQueueItem.ContentType.POST,
            status=ModQueueItem.Status.NEEDS_REVIEW,
        )
        client.force_login(self.owner)

        response = client.post(
            reverse("mod_action", kwargs={"community_slug": self.community.slug}),
            {
                "post_id": self.post.id,
                "action_type": ModAction.ActionType.APPROVE_POST,
                "reason_code": "ok",
                "reason_text": "Approved",
            },
            HTTP_HX_REQUEST="true",
        )

        self.post.refresh_from_db()
        assert response.status_code == 200
        assert ModAction.ActionType.APPROVE_POST in response.content.decode()
        assert self.post.is_removed is False

    def test_report_content_invalid_target_returns_forbidden(self, client):
        client.force_login(self.reporter)

        response = client.post(reverse("report_content"), {"post_id": 999999, "reason": "spam"})

        assert response.status_code == 403

    @pytest.mark.parametrize("duration", ["abc", "-2"])
    def test_ban_user_rejects_invalid_duration(self, client, duration):
        client.force_login(self.owner)

        response = client.post(
            reverse("ban_user", kwargs={"community_slug": self.community.slug}),
            {"handle": self.member.handle, "duration": duration, "reason": "Bad actor"},
        )

        assert response.status_code == 400

    def test_mod_mail_thread_denies_unrelated_user(self, client):
        thread = ModMail.objects.create(community=self.community, subject="Question", created_by=self.reporter)
        client.force_login(self.other)

        response = client.get(
            reverse("mod_mail_thread", kwargs={"community_slug": self.community.slug, "thread_id": thread.id})
        )

        assert response.status_code == 403

    def test_mod_mail_create_invalid_form_rerenders(self, client):
        client.force_login(self.reporter)

        response = client.post(reverse("mod_mail_create", kwargs={"community_slug": self.community.slug}), {"subject": ""})

        assert response.status_code == 200
        assert "This field is required." in response.content.decode()

    def test_removal_reasons_manage_invalid_form_rerenders(self, client):
        client.force_login(self.owner)

        response = client.post(
            reverse("removal_reasons_manage", kwargs={"community_slug": self.community.slug}),
            {"code": "", "title": "", "message_md": "", "order": ""},
        )

        assert response.status_code == 200
        assert "This field is required." in response.content.decode()

    @pytest.mark.parametrize(
        ("name", "kwargs"),
        [
            ("report_content", {}),
            ("mod_queue", {"community_slug": "slug"}),
            ("mod_log", {"community_slug": "slug"}),
            ("mod_mail_list", {"community_slug": "slug"}),
            ("mod_mail_create", {"community_slug": "slug"}),
            ("mod_mail_thread", {"community_slug": "slug", "thread_id": 1}),
            ("removal_reasons_manage", {"community_slug": "slug"}),
            ("mod_action", {"community_slug": "slug"}),
            ("ban_user", {"community_slug": "slug"}),
        ],
    )
    def test_moderation_urls_reverse_and_resolve(self, name, kwargs):
        path = reverse(name, kwargs=kwargs)

        assert resolve(path).view_name == name

