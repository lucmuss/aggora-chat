import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import AgentIdentityProvider, Notification, UserBadge

User = get_user_model()


def make_user(**overrides):
    base = {
        "username": f"user_{timezone.now().timestamp()}",
        "email": f"user_{timezone.now().timestamp()}@example.com",
        "password": "password123",
        "handle": None,
    }
    base.update(overrides)
    return User.objects.create_user(**base)


@pytest.mark.django_db
class TestUserModel:
    def test_total_karma_returns_sum_of_post_and_comment_karma(self):
        user = make_user(post_karma=4, comment_karma=7)

        assert user.total_karma() == 11

    def test_str_prefers_handle_then_email_then_username(self):
        with_handle = make_user(username="withhandle", email="withhandle@example.com", handle="withhandle")
        with_email = make_user(username="withemail", email="withemail@example.com", handle=None)
        with_username = make_user(username="onlyusername", email="", handle=None)

        assert str(with_handle) == "withhandle"
        assert str(with_email) == "withemail@example.com"
        assert str(with_username) == "onlyusername"

    def test_handle_validator_rejects_invalid_formats(self):
        invalid_handles = ["UPPER", "has space", "!!", "ab", "waytoolong_handle_name_that_exceeds"]

        for handle in invalid_handles:
            user = User(username=f"user_{handle}", email=f"{hash(handle)}@example.com", handle=handle)
            with pytest.raises(ValidationError):
                user.full_clean()

    def test_default_account_flags_are_set(self):
        user = make_user()

        assert user.profile_visibility == User.ProfileVisibility.PUBLIC
        assert user.email_notifications_enabled is False
        assert user.push_notifications_enabled is False
        assert user.notify_on_replies is True
        assert user.notify_on_follows is True
        assert user.notify_on_challenges is True
        assert user.mfa_totp_enabled is False
        assert user.onboarding_completed is False


@pytest.mark.django_db
class TestAgentIdentityProviderModel:
    def test_str_returns_name(self):
        provider = AgentIdentityProvider.objects.create(
            name="Trusted Agents",
            issuer_url="https://issuer.example",
        )

        assert str(provider) == "Trusted Agents"

    def test_default_status_and_ordering(self):
        later = AgentIdentityProvider.objects.create(name="Zulu", issuer_url="https://zulu.example")
        AgentIdentityProvider.objects.create(name="Alpha", issuer_url="https://alpha.example")

        assert later.status == AgentIdentityProvider.Status.PENDING
        assert list(AgentIdentityProvider.objects.values_list("name", flat=True)) == ["Alpha", "Zulu"]


@pytest.mark.django_db
class TestNotificationModel:
    def test_notification_defaults_and_optional_relations(self):
        user = make_user(handle="notifyme")
        notification = Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.POST_REPLY,
            message="Someone replied",
        )

        assert notification.actor is None
        assert notification.community is None
        assert notification.post is None
        assert notification.comment is None
        assert notification.is_read is False
        assert notification.emailed_at is None

    def test_notification_ordering_is_newest_first(self):
        user = make_user(handle="ordered")
        older = Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.POST_REPLY,
            message="Older",
        )
        newer = Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.COMMENT_REPLY,
            message="Newer",
        )

        assert list(Notification.objects.values_list("id", flat=True)[:2]) == [newer.id, older.id]

    def test_notification_str_uses_user_and_message(self):
        user = make_user(handle="stringy")
        notification = Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.POST_REPLY,
            message="Readable",
        )

        assert str(notification) == "stringy: Readable"


@pytest.mark.django_db
class TestUserBadgeModel:
    def test_userbadge_unique_constraint_prevents_duplicate_code_for_same_user(self):
        user = make_user(handle="badged")
        UserBadge.objects.create(user=user, code=UserBadge.BadgeCode.FIRST_STEPS, title="First Steps")

        with pytest.raises(IntegrityError):
            UserBadge.objects.create(user=user, code=UserBadge.BadgeCode.FIRST_STEPS, title="Duplicate")

    def test_userbadge_ordering_is_newest_first(self):
        user = make_user(handle="badgeorder")
        first = UserBadge.objects.create(user=user, code=UserBadge.BadgeCode.FIRST_STEPS, title="First")
        second = UserBadge.objects.create(user=user, code=UserBadge.BadgeCode.PROFILE_READY, title="Second")

        assert list(UserBadge.objects.values_list("id", flat=True)[:2]) == [second.id, first.id]

    def test_userbadge_str_includes_user_and_title(self):
        user = make_user(handle="showbadge")
        badge = UserBadge.objects.create(user=user, code=UserBadge.BadgeCode.FIRST_POST, title="First Post")

        assert str(badge) == "showbadge: First Post"
