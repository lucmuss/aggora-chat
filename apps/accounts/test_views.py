import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import Notification
from apps.communities.models import Community, CommunityInvite, CommunityMembership
from apps.posts.models import Post


User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "view_user"),
        "email": overrides.pop("email", "view_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", None),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug, creator, **overrides):
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "Community for account view tests",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestAccountViews:
    def test_profile_private_visibility_hides_content_from_other_users(self, client):
        owner = make_user(username="privateowner", email="privateowner@example.com", handle="privateowner")
        owner.profile_visibility = User.ProfileVisibility.PRIVATE
        owner.save(update_fields=["profile_visibility"])
        viewer = make_user(username="viewerprivate", email="viewerprivate@example.com", handle="viewerprivate")
        client.force_login(viewer)

        response = client.get(reverse("profile", kwargs={"handle": owner.handle}))

        assert response.status_code == 200
        assert "This profile is not publicly visible right now." in response.content.decode()

    def test_profile_members_visibility_hides_from_anonymous(self, client):
        owner = make_user(username="membersowner", email="membersowner@example.com", handle="membersowner")
        owner.profile_visibility = User.ProfileVisibility.MEMBERS
        owner.save(update_fields=["profile_visibility"])

        response = client.get(reverse("profile", kwargs={"handle": owner.handle}))

        assert response.status_code == 200
        assert "This profile is not publicly visible right now." in response.content.decode()

    def test_toggle_follow_get_redirects_without_changing_state(self, client):
        user = make_user(username="followget", email="followget@example.com", handle="followget")
        other = make_user(username="otherget", email="otherget@example.com", handle="otherget")
        client.force_login(user)

        response = client.get(reverse("toggle_follow", kwargs={"handle": other.handle}))

        assert response.status_code == 302
        assert not user.followed_users.filter(pk=other.pk).exists()

    def test_toggle_block_get_redirects_without_changing_state(self, client):
        user = make_user(username="blockget", email="blockget@example.com", handle="blockget")
        other = make_user(username="otherblock", email="otherblock@example.com", handle="otherblock")
        client.force_login(user)

        response = client.get(reverse("toggle_block", kwargs={"handle": other.handle}))

        assert response.status_code == 302
        assert not user.blocked_users.filter(pk=other.pk).exists()

    def test_toggle_theme_sets_cookie_and_redirects(self, client):
        response = client.get(reverse("toggle_theme"), {"next": reverse("home")})

        assert response.status_code == 302
        assert response.url == reverse("home")
        assert response.cookies["agora_theme"].value == "dark"

    def test_handle_setup_redirects_completed_user_to_home(self, client):
        user = make_user(username="handled", email="handled@example.com", handle="handled", onboarding_completed=True)
        client.force_login(user)

        response = client.get(reverse("handle_setup"))

        assert response.status_code == 302
        assert response.url == reverse("home")

    def test_notifications_view_handles_empty_state(self, client):
        user = make_user(username="emptyalerts", email="emptyalerts@example.com", handle="emptyalerts")
        client.force_login(user)

        response = client.get(reverse("notifications"))

        assert response.status_code == 200
        assert list(response.context["notifications"]) == []

    def test_referrals_view_handles_no_memberships(self, client):
        user = make_user(username="noreferrals", email="noreferrals@example.com", handle="noreferrals")
        client.force_login(user)

        response = client.get(reverse("account_referrals"))

        assert response.status_code == 200
        assert list(response.context["referral_cards"]) == []
        assert response.context["total_referrals"] == 0

    def test_start_with_friends_invalid_form_rerenders_errors(self, client):
        user = make_user(username="onboardinginvalid", email="onboardinginvalid@example.com", handle="onboardinginvalid")
        community = make_community("onboarding-invalid", user)
        client.force_login(user)

        response = client.post(
            reverse("start_with_friends"),
            {
                "communities": [community.pk],
                "first_post_community": community.pk,
                "first_contribution_type": "post",
                "friend_emails": "not-an-email",
            },
        )

        assert response.status_code == 200
        assert "friend_emails" in response.context["form"].errors
        user.refresh_from_db()
        assert user.onboarding_completed is False

    def test_start_with_friends_redeems_pending_invite(self, client):
        owner = make_user(username="inviteowner", email="inviteowner@example.com", handle="inviteowner")
        joiner = make_user(username="invitejoiner", email="invitejoiner@example.com", handle="invitejoiner")
        community = make_community("invite-community", owner)
        invite = CommunityInvite.objects.create(community=community, created_by=owner, token="token123")
        client.force_login(joiner)
        session = client.session
        session["pending_invite_token"] = invite.token
        session.save()

        response = client.post(
            reverse("start_with_friends"),
            {
                "communities": [],
                "first_contribution_type": "post",
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("create_post", kwargs={"community_slug": community.slug})
        assert CommunityMembership.objects.filter(user=joiner, community=community).exists()

    def test_account_settings_view_gracefully_handles_missing_allauth_models(self, client, monkeypatch):
        user = make_user(username="settingsgrace", email="settingsgrace@example.com", handle="settingsgrace")
        client.force_login(user)
        monkeypatch.setattr("apps.accounts.views.EmailAddress", None)
        monkeypatch.setattr("apps.accounts.views.SocialAccount", None)

        response = client.get(reverse("account_settings"))

        assert response.status_code == 200
        assert response.context["connected_accounts"] == []
        assert response.context["email_addresses"] == []

    def test_mfa_setup_invalid_code_adds_form_error(self, client):
        user = make_user(username="mfasetup", email="mfasetup@example.com", handle="mfasetup")
        client.force_login(user)

        response = client.post(reverse("account_mfa_setup"), {"code": "000000"})

        assert response.status_code == 200
        assert "code" in response.context["form"].errors

    def test_mfa_disable_requires_post(self, client):
        user = make_user(username="mfadisable", email="mfadisable@example.com", handle="mfadisable")
        client.force_login(user)

        response = client.get(reverse("account_mfa_disable"))

        assert response.status_code == 403

    def test_mfa_disable_invalid_code_redirects_back_to_setup(self, client):
        user = make_user(
            username="mfainvalid",
            email="mfainvalid@example.com",
            handle="mfainvalid",
            mfa_totp_secret="JBSWY3DPEHPK3PXP",
            mfa_totp_enabled=True,
        )
        client.force_login(user)

        response = client.post(reverse("account_mfa_disable"), {"code": "000000"})

        assert response.status_code == 302
        assert response.url == reverse("account_mfa_setup")
        user.refresh_from_db()
        assert user.mfa_totp_enabled is True

    def test_notifications_view_marks_only_unread_notifications(self, client):
        user = make_user(username="notifuser", email="notifuser@example.com", handle="notifuser")
        Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.POST_REPLY,
            message="Unread",
            is_read=False,
        )
        Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.COMMENT_REPLY,
            message="Read",
            is_read=True,
        )
        client.force_login(user)

        response = client.get(reverse("notifications"))

        assert response.status_code == 200
        assert Notification.objects.filter(user=user, is_read=False).count() == 0

    @override_settings(LOGOUT_REDIRECT_URL="/")
    def test_account_settings_context_uses_set_password_for_users_without_usable_password(self, client):
        user = make_user(username="unusable", email="unusable@example.com", handle="unusable")
        user.set_unusable_password()
        user.save(update_fields=["password"])
        client.force_login(user)

        response = client.get(reverse("account_settings"))

        assert response.status_code == 200
        assert response.context["password_url_name"] == "account_set_password"

    def test_profile_me_redirects_anonymous_user_to_login(self, client):
        response = client.get(reverse("profile", kwargs={"handle": "me"}))

        assert response.status_code == 302
        assert reverse("account_login") in response.url

    def test_profile_me_redirects_handleless_user_to_handle_setup(self, client):
        user = make_user(username="mehandleless", email="mehandleless@example.com", handle=None)
        client.force_login(user)

        response = client.get(reverse("profile", kwargs={"handle": "me"}))

        assert response.status_code == 302
        assert response.url == reverse("handle_setup")
