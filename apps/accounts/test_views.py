from datetime import date
import pytest
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import Notification
from apps.communities.models import Community, CommunityInvite, CommunityMembership
from apps.posts.models import Comment, Post

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

    def test_profile_shows_total_awards_received(self, client):
        owner = make_user(username="awardprofile", email="awardprofile@example.com", handle="awardprofile")
        giver = make_user(username="awardgiver", email="awardgiver@example.com", handle="awardgiver")
        community = make_community("award-profile-community", owner)
        post = Post.objects.create(community=community, author=owner, post_type="text", title="Awarded thread", body_md="Body", award_count=2)
        Comment.objects.create(post=post, author=owner, body_md="Awarded comment", body_html="<p>Awarded comment</p>", award_count=1)
        client.force_login(giver)

        response = client.get(reverse("profile", kwargs={"handle": owner.handle}))

        assert response.status_code == 200
        assert "Awards received" in response.content.decode()
        assert ">3<" in response.content.decode()

    def test_profile_shows_city_region_and_country(self, client):
        owner = make_user(
            username="locationprofile",
            email="locationprofile@example.com",
            handle="locationprofile",
            country="Germany",
            region="Berlin",
            city="Berlin",
        )
        viewer = make_user(username="locationviewer", email="locationviewer@example.com", handle="locationviewer")
        client.force_login(viewer)

        response = client.get(reverse("profile", kwargs={"handle": owner.handle}))

        assert response.status_code == 200
        assert "Berlin" in response.content.decode()
        assert "Germany" in response.content.decode()

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

    def test_notifications_view_filters_replies(self, client):
        user = make_user(username="replyalerts", email="replyalerts@example.com", handle="replyalerts")
        Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.POST_REPLY,
            message="A reply",
        )
        Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.FOLLOWED_USER_JOINED,
            message="A follow event",
        )
        client.force_login(user)

        response = client.get(reverse("notifications"), {"filter": "replies"})

        assert response.status_code == 200
        assert len(response.context["notifications"]) == 1
        assert response.context["notification_filter"] == "replies"

    def test_notifications_view_filters_mentions(self, client):
        user = make_user(username="mentionalerts", email="mentionalerts@example.com", handle="mentionalerts")
        Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.MENTION,
            message="You were mentioned",
        )
        Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.FOLLOWED_USER_JOINED,
            message="A follow event",
        )
        client.force_login(user)

        response = client.get(reverse("notifications"), {"filter": "mentions"})

        assert response.status_code == 200
        assert len(response.context["notifications"]) == 1
        assert response.context["notification_filter"] == "mentions"

    def test_notification_toggle_read_flips_state(self, client):
        user = make_user(username="toggleread", email="toggleread@example.com", handle="toggleread")
        notification = Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.POST_REPLY,
            message="Unread",
            is_read=False,
        )
        client.force_login(user)

        response = client.post(reverse("notification_toggle_read", kwargs={"notification_id": notification.id}))

        assert response.status_code == 302
        notification.refresh_from_db()
        assert notification.is_read is True

    def test_notifications_mark_all_read_marks_only_current_user_items(self, client):
        user = make_user(username="markall", email="markall@example.com", handle="markall")
        other = make_user(username="markall_other", email="markall_other@example.com", handle="markall_other")
        Notification.objects.create(user=user, notification_type=Notification.NotificationType.POST_REPLY, message="One")
        Notification.objects.create(user=other, notification_type=Notification.NotificationType.POST_REPLY, message="Two")
        client.force_login(user)

        response = client.post(reverse("notifications_mark_all_read"))

        assert response.status_code == 302
        assert Notification.objects.filter(user=user, is_read=False).count() == 0
        assert Notification.objects.filter(user=other, is_read=False).count() == 1

    def test_browser_notifications_feed_returns_only_recent_unread_items(self, client):
        user = make_user(
            username="pushfeed",
            email="pushfeed@example.com",
            handle="pushfeed",
            push_notifications_enabled=True,
        )
        older = Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.POST_REPLY,
            message="Older",
        )
        newer = Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.MENTION,
            message="Newer",
        )
        client.force_login(user)

        response = client.get(
            reverse("browser_notifications_feed"),
            {"since": older.created_at.isoformat()},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["notifications"]) == 1
        assert payload["notifications"][0]["message"] == "Newer"

    def test_browser_notifications_feed_respects_push_setting(self, client):
        user = make_user(username="nopushfeed", email="nopushfeed@example.com", handle="nopushfeed")
        Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.POST_REPLY,
            message="Ignored",
        )
        client.force_login(user)

        response = client.get(reverse("browser_notifications_feed"))

        assert response.status_code == 200
        assert response.json() == {"notifications": []}

    def test_mention_search_prefers_followed_and_community_members(self, client):
        user = make_user(username="searchowner", email="searchowner@example.com", handle="searchowner")
        followed = make_user(username="ariane", email="ariane@example.com", handle="ariane", display_name="Ariane Keller")
        community_member = make_user(username="arihelper", email="arihelper@example.com", handle="arihelper", display_name="Ari Helper")
        outsider = make_user(username="otherariane", email="otherariane@example.com", handle="otherariane", display_name="Other Ari")
        community = make_community("mention-community", user)
        user.followed_users.add(followed)
        CommunityMembership.objects.create(user=community_member, community=community)
        client.force_login(user)

        response = client.get(reverse("mention_search"), {"q": "ari", "community_slug": community.slug})

        assert response.status_code == 200
        handles = [item["handle"] for item in response.json()["results"]]
        assert "ariane" in handles
        assert "arihelper" in handles
        assert "otherariane" in handles

    def test_referrals_view_handles_no_memberships(self, client):
        user = make_user(username="noreferrals", email="noreferrals@example.com", handle="noreferrals")
        client.force_login(user)

        response = client.get(reverse("account_referrals"))

        assert response.status_code == 200
        assert list(response.context["referral_cards"]) == []
        assert response.context["referral_stats"]["total_referrals"] == 0

    def test_referrals_view_exposes_featured_card_and_invite_stats(self, client):
        user = make_user(username="refstats", email="refstats@example.com", handle="refstats")
        community = make_community("ref-stats", user)
        CommunityMembership.objects.create(user=user, community=community)
        invite = CommunityInvite.objects.create(community=community, created_by=user, token="refstats-token", usage_count=2)
        client.force_login(user)

        response = client.get(reverse("account_referrals"))

        assert response.status_code == 200
        assert response.context["featured_referral_card"].invite.id == invite.id
        assert response.context["referral_stats"]["total_referrals"] == 2
        assert response.context["referral_stats"]["total_invite_links"] == 1

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

    def test_account_settings_context_exposes_regions_and_places_provider(self, client):
        user = make_user(username="settingslocation", email="settingslocation@example.com", handle="settingslocation")
        client.force_login(user)

        response = client.get(reverse("account_settings"))

        assert response.status_code == 200
        assert "regions_by_country_json" in response.context
        assert "google_places_api_key" in response.context

    def test_mfa_setup_invalid_code_adds_form_error(self, client):
        user = make_user(username="mfasetup", email="mfasetup@example.com", handle="mfasetup")
        client.force_login(user)

        response = client.post(reverse("account_mfa_setup"), {"code": "000000"})

        assert response.status_code == 200
        assert "code" in response.context["form"].errors

    def test_mfa_setup_explains_admin_requirement_when_next_points_to_admin(self, client):
        user = make_user(username="mfaadminhint", email="mfaadminhint@example.com", handle="mfaadminhint", is_staff=True)
        client.force_login(user)

        response = client.get(reverse("account_mfa_setup"), {"next": "/admin/"})

        assert response.status_code == 200
        assert response.context["required_for_admin"] is True
        assert "Admin access needs 2FA first." in response.content.decode()

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

    def test_notifications_view_preserves_unread_state_until_user_acts(self, client):
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
        assert Notification.objects.filter(user=user, is_read=False).count() == 1

    @override_settings(LOGOUT_REDIRECT_URL="/")
    def test_account_settings_context_uses_set_password_for_users_without_usable_password(self, client):
        user = make_user(username="unusable", email="unusable@example.com", handle="unusable")
        user.set_unusable_password()
        user.save(update_fields=["password"])
        client.force_login(user)

        response = client.get(reverse("account_settings"))

        assert response.status_code == 200
        assert response.context["password_url_name"] == "account_set_password"

    def test_account_settings_save_updates_theme_cookie_and_primary_email(self, client):
        user = make_user(username="themeuser", email="themeuser@example.com", handle="themeuser")
        client.force_login(user)

        response = client.post(
            reverse("account_settings"),
            {
                "handle": "themeuser",
                "email": "newthemeuser@example.com",
                "display_name": "Theme User",
                "bio": "",
                "birth_date": "",
                "country": "Germany",
                "profile_visibility": User.ProfileVisibility.PUBLIC,
                "preferred_theme": User.PreferredTheme.DARK,
                "email_notifications_enabled": "",
                "push_notifications_enabled": "",
                "notify_on_replies": "on",
                "notify_on_follows": "on",
                "notify_on_challenges": "on",
            },
        )

        user.refresh_from_db()
        assert response.status_code == 302
        assert response.cookies["agora_theme"].value == "dark"
        assert user.email == "newthemeuser@example.com"

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_profile_shows_avatar_country_and_age_when_present(self, client):
        user = make_user(
            username="profilemeta",
            email="profilemeta@example.com",
            handle="profilemeta",
            country="Germany",
        )
        user.birth_date = date(1990, 1, 1)
        user.avatar = SimpleUploadedFile("avatar.png", b"fake-image", content_type="image/png")
        user.save(update_fields=["birth_date", "avatar", "country"])

        response = client.get(reverse("profile", kwargs={"handle": user.handle}))

        assert response.status_code == 200
        assert "Germany" in response.content.decode()
        assert 'src="/media/avatars/avatar' in response.content.decode()

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

    def test_record_post_share_marks_first_share_timestamp(self, client):
        user = make_user(username="sharetracker", email="sharetracker@example.com", handle="sharetracker")
        community = make_community("share-community", user)
        post = Post.objects.create(
            community=community,
            author=user,
            post_type="text",
            title="A thread worth sharing",
            body_md="Details",
        )
        client.force_login(user)

        response = client.post(reverse("record_post_share", kwargs={"post_id": post.id}))

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.first_post_share_at is not None
