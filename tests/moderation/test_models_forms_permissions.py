import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.communities.models import Community, CommunityMembership
from apps.moderation.forms import ModMailCreateForm, ModMailReplyForm, RemovalReasonForm
from apps.moderation.models import Ban, CommunityAgentSettings, ModMail, ModMailMessage
from apps.moderation.permissions import ModPermission, has_mod_permission
from apps.moderation.utils import is_user_banned

User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "moderation_model_user"),
        "email": overrides.pop("email", "moderation_model_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "moderation_model_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="moderation-models", creator=None, **overrides):
    creator = creator or make_user(
        username=f"{slug}_creator",
        email=f"{slug}_creator@example.com",
        handle=f"{slug}_creator",
    )
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "Moderation model tests",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestModerationModelsFormsPermissions:
    def test_community_agent_settings_str_includes_community_slug(self):
        community = make_community("agent-settings")
        settings_obj = CommunityAgentSettings.objects.create(community=community)

        assert str(settings_obj) == "Agent settings for c/agent-settings"

    def test_modmail_and_messages_respect_declared_ordering(self):
        community = make_community("modmail-ordering")
        author = community.creator
        older = ModMail.objects.create(community=community, subject="Older", created_by=author)
        newer = ModMail.objects.create(community=community, subject="Newer", created_by=author)
        ModMailMessage.objects.create(thread=newer, author=author, body_md="First", body_html="<p>First</p>")
        ModMailMessage.objects.create(thread=newer, author=author, body_md="Second", body_html="<p>Second</p>")

        assert list(ModMail.objects.values_list("subject", flat=True)[:2]) == ["Newer", "Older"]
        assert list(newer.messages.values_list("body_md", flat=True)) == ["First", "Second"]
        assert str(older) != ""

    def test_modmail_reply_form_renders_body_html_on_save(self):
        community = make_community("reply-form")
        thread = ModMail.objects.create(community=community, subject="Appeal", created_by=community.creator)
        form = ModMailReplyForm({"body_md": "**Please review**"})

        assert form.is_valid() is True
        message = form.save(commit=False)
        message.thread = thread
        message.author = community.creator
        message.is_mod_reply = False
        message.save()

        assert "<strong>Please review</strong>" in message.body_html

    def test_modmail_create_and_removal_reason_forms_validate_required_fields(self):
        valid_mail = ModMailCreateForm({"subject": "Help", "body_md": "Please check this"})
        invalid_mail = ModMailCreateForm({"subject": "", "body_md": ""})
        valid_reason = RemovalReasonForm(
            {"code": "spam", "title": "Spam", "message_md": "Removed as spam", "order": 2}
        )
        invalid_reason = RemovalReasonForm({"code": "", "title": "", "message_md": "", "order": ""})

        assert valid_mail.is_valid() is True
        assert invalid_mail.is_valid() is False
        assert "subject" in invalid_mail.errors
        assert valid_reason.is_valid() is True
        assert invalid_reason.is_valid() is False

    def test_has_mod_permission_handles_staff_owner_agent_mod_and_non_member(self):
        owner = make_user(username="owner_perm", email="owner_perm@example.com", handle="owner_perm")
        moderator = make_user(username="moderator_perm", email="moderator_perm@example.com", handle="moderator_perm")
        agent_mod = make_user(username="agent_perm", email="agent_perm@example.com", handle="agent_perm")
        outsider = make_user(username="outsider_perm", email="outsider_perm@example.com", handle="outsider_perm")
        staff = make_user(username="staff_perm", email="staff_perm@example.com", handle="staff_perm", is_staff=True)
        community = make_community("mod-permissions", creator=owner)
        CommunityMembership.objects.create(user=owner, community=community, role=CommunityMembership.Role.OWNER)
        CommunityMembership.objects.create(
            user=moderator,
            community=community,
            role=CommunityMembership.Role.MODERATOR,
        )
        CommunityMembership.objects.create(
            user=agent_mod,
            community=community,
            role=CommunityMembership.Role.AGENT_MOD,
        )

        assert has_mod_permission(staff, community, ModPermission.MANAGE_SETTINGS) is True
        assert has_mod_permission(owner, community, ModPermission.MOD_MAIL) is True
        assert has_mod_permission(moderator, community, ModPermission.MANAGE_USERS) is True
        assert has_mod_permission(agent_mod, community, ModPermission.VIEW_MOD_QUEUE) is True
        assert has_mod_permission(agent_mod, community, ModPermission.MANAGE_USERS) is False
        assert has_mod_permission(outsider, community, ModPermission.VIEW_MOD_LOG) is False

    def test_is_user_banned_handles_permanent_active_expired_and_anonymous_users(self):
        user = make_user(username="banned_user", email="banned_user@example.com", handle="banned_user")
        community = make_community("ban-checks")
        anonymous = type("Anon", (), {"is_authenticated": False})()

        assert is_user_banned(anonymous, community) is False
        assert is_user_banned(user, community) is False

        permanent = Ban.objects.create(community=community, user=user, banned_by=community.creator, is_permanent=True)
        assert is_user_banned(user, community) is True
        permanent.delete()

        active = Ban.objects.create(
            community=community,
            user=user,
            banned_by=community.creator,
            is_permanent=False,
            expires_at=timezone.now() + timezone.timedelta(days=1),
        )
        assert is_user_banned(user, community) is True
        active.delete()

        expiring = Ban.objects.create(
            community=community,
            user=user,
            banned_by=community.creator,
            is_permanent=False,
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        assert is_user_banned(user, community) is False
        assert Ban.objects.filter(pk=expiring.pk).exists() is False

        null_expiry = Ban.objects.create(
            community=community,
            user=user,
            banned_by=community.creator,
            is_permanent=False,
            expires_at=None,
        )
        assert is_user_banned(user, community) is True
        assert Ban.objects.filter(pk=null_expiry.pk).exists() is True

