import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.communities.models import (
    Community,
    CommunityChallenge,
    CommunityInvite,
    CommunityMembership,
    CommunityWikiPage,
)
from apps.moderation.models import ModQueueItem
from apps.posts.models import Post

User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "community_view_user"),
        "email": overrides.pop("email", "community_view_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "community_view_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="community-view", creator=None, **overrides):
    creator = creator or make_user(username=f"{slug}_creator", email=f"{slug}_creator@example.com", handle=f"{slug}_creator")
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "Community view tests",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestCommunityViews:
    def test_create_community_get_requires_login(self, client):
        response = client.get(reverse("create_community"))

        assert response.status_code == 302
        assert reverse("account_login") in response.url

    def test_create_community_invalid_post_rerenders_form(self, client):
        user = make_user(username="creator_invalid", email="creator_invalid@example.com", handle="creator_invalid")
        client.force_login(user)

        response = client.post(reverse("create_community"), {"name": "", "slug": "", "title": ""})

        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["form"].errors

    def test_toggle_membership_get_returns_403(self, client):
        user = make_user(username="toggle_get", email="toggle_get@example.com", handle="toggle_get")
        community = make_community("toggle-get", creator=user)
        client.force_login(user)

        response = client.get(reverse("toggle_membership", kwargs={"slug": community.slug}))

        assert response.status_code == 403

    def test_toggle_membership_restricted_community_renders_access_denied(self, client):
        owner = make_user(username="restricted_owner", email="restricted_owner@example.com", handle="restricted_owner")
        user = make_user(username="restricted_user", email="restricted_user@example.com", handle="restricted_user")
        community = make_community("restricted-community", creator=owner, community_type=Community.CommunityType.RESTRICTED)
        client.force_login(user)

        response = client.post(reverse("toggle_membership", kwargs={"slug": community.slug}))

        assert response.status_code == 403
        assert "This community needs an invite" in response.content.decode()

    def test_toggle_membership_owner_leave_renders_error_page(self, client):
        owner = make_user(username="owner_toggle", email="owner_toggle@example.com", handle="owner_toggle")
        community = make_community("owner-community", creator=owner)
        CommunityMembership.objects.create(user=owner, community=community, role=CommunityMembership.Role.OWNER)
        client.force_login(owner)

        response = client.post(reverse("toggle_membership", kwargs={"slug": community.slug}))

        assert response.status_code == 403
        assert "Owners cannot leave their own community." in response.content.decode()

    def test_discovery_filters_private_communities_for_anonymous_and_query(self, client):
        public = make_community("public-discovery")
        private = make_community("private-discovery", community_type=Community.CommunityType.PRIVATE)

        response = client.get(reverse("community_discovery"), {"q": "public"})

        assert response.status_code == 200
        assert public.title in response.content.decode()
        assert private.title not in response.content.decode()

    def test_community_settings_requires_permission(self, client):
        owner = make_user(username="settings_owner", email="settings_owner@example.com", handle="settings_owner")
        outsider = make_user(username="settings_outsider", email="settings_outsider@example.com", handle="settings_outsider")
        community = make_community("settings-community", creator=owner)
        client.force_login(outsider)

        response = client.get(reverse("community_settings", kwargs={"slug": community.slug}))

        assert response.status_code == 403
        assert "Moderator permissions required" in response.content.decode()

    def test_community_settings_invalid_post_rerenders_form(self, client):
        owner = make_user(username="settings_owner2", email="settings_owner2@example.com", handle="settings_owner2", mfa_totp_enabled=True)
        community = make_community("settings-invalid", creator=owner)
        CommunityMembership.objects.create(user=owner, community=community, role=CommunityMembership.Role.OWNER)
        client.force_login(owner)

        response = client.post(reverse("community_settings", kwargs={"slug": community.slug}), {"title": ""})

        assert response.status_code == 200
        assert response.context["form"].errors

    def test_community_landing_private_community_returns_403(self, client):
        owner = make_user(username="landing_owner", email="landing_owner@example.com", handle="landing_owner")
        community = make_community("landing-private", creator=owner, community_type=Community.CommunityType.PRIVATE)

        response = client.get(reverse("community_landing", kwargs={"slug": community.slug}))

        assert response.status_code == 403

    def test_community_share_card_private_community_returns_403(self, client):
        owner = make_user(username="share_owner", email="share_owner@example.com", handle="share_owner")
        community = make_community("share-private", creator=owner, community_type=Community.CommunityType.PRIVATE)

        response = client.get(reverse("community_share_card", kwargs={"slug": community.slug}))

        assert response.status_code == 403

    def test_community_invite_get_sets_pending_token_for_anonymous(self, client):
        owner = make_user(username="invite_owner", email="invite_owner@example.com", handle="invite_owner")
        community = make_community("invite-anon", creator=owner)
        invite = CommunityInvite.objects.create(community=community, created_by=owner, token="anon-token")

        response = client.get(reverse("community_invite", kwargs={"slug": community.slug, "token": invite.token}))

        assert response.status_code == 200
        assert client.session["pending_invite_token"] == invite.token

    def test_join_community_challenge_redirects_to_next_url(self, client):
        owner = make_user(username="challenge_owner", email="challenge_owner@example.com", handle="challenge_owner")
        member = make_user(username="challenge_member", email="challenge_member@example.com", handle="challenge_member")
        community = make_community("challenge-next", creator=owner)
        CommunityMembership.objects.create(user=member, community=community)
        challenge = CommunityChallenge.objects.create(
            community=community,
            title="Join Next",
            prompt_md="Prompt",
            starts_at=timezone.now() - timezone.timedelta(hours=1),
            ends_at=timezone.now() + timezone.timedelta(hours=2),
        )
        client.force_login(member)

        response = client.post(
            reverse("community_challenge_join", kwargs={"slug": community.slug, "challenge_id": challenge.id}),
            {"next": reverse("community_landing", kwargs={"slug": community.slug})},
        )

        assert response.status_code == 302
        assert response.url == reverse("community_landing", kwargs={"slug": community.slug})

    def test_join_community_challenge_denies_without_membership(self, client):
        owner = make_user(username="challenge_deny_owner", email="challenge_deny_owner@example.com", handle="challenge_deny_owner")
        outsider = make_user(username="challenge_outsider", email="challenge_outsider@example.com", handle="challenge_outsider")
        community = make_community("challenge-deny", creator=owner, community_type=Community.CommunityType.RESTRICTED)
        challenge = CommunityChallenge.objects.create(
            community=community,
            title="No Access",
            prompt_md="Prompt",
            starts_at=timezone.now() - timezone.timedelta(hours=1),
            ends_at=timezone.now() + timezone.timedelta(hours=2),
        )
        client.force_login(outsider)

        response = client.post(reverse("community_challenge_join", kwargs={"slug": community.slug, "challenge_id": challenge.id}))

        assert response.status_code == 403
        assert "Join the community first" in response.content.decode()

    def test_wiki_page_renders_without_existing_page(self, client):
        community = make_community("wiki-empty")

        response = client.get(reverse("community_wiki_home", kwargs={"slug": community.slug}))

        assert response.status_code == 200
        assert response.context["page"] is None

    def test_wiki_page_private_community_denies_anonymous_user(self, client):
        owner = make_user(username="wiki_private_owner", email="wiki_private_owner@example.com", handle="wiki_private_owner")
        community = make_community("wiki-private", creator=owner, community_type=Community.CommunityType.PRIVATE)

        response = client.get(reverse("community_wiki_home", kwargs={"slug": community.slug}))

        assert response.status_code == 403
        assert "only visible to members" in response.content.decode()

    def test_wiki_edit_requires_permission(self, client):
        owner = make_user(username="wiki_owner", email="wiki_owner@example.com", handle="wiki_owner")
        outsider = make_user(username="wiki_outsider", email="wiki_outsider@example.com", handle="wiki_outsider")
        community = make_community("wiki-denied", creator=owner)
        client.force_login(outsider)

        response = client.get(reverse("community_wiki_edit_home", kwargs={"slug": community.slug}))

        assert response.status_code == 403
        assert "Moderator permissions required" in response.content.decode()

    def test_wiki_edit_invalid_post_rerenders_form(self, client):
        owner = make_user(username="wiki_editor", email="wiki_editor@example.com", handle="wiki_editor", mfa_totp_enabled=True)
        community = make_community("wiki-invalid", creator=owner)
        CommunityMembership.objects.create(user=owner, community=community, role=CommunityMembership.Role.OWNER)
        existing = CommunityWikiPage.objects.create(community=community, slug="home", title="Home")
        client.force_login(owner)

        response = client.post(
            reverse("community_wiki_edit_home", kwargs={"slug": community.slug}),
            {"slug": "home", "title": "", "body_md": "Body"},
        )

        assert response.status_code == 200
        assert response.context["form"].errors
        existing.refresh_from_db()
        assert existing.title == "Home"

    def test_community_landing_shows_challenge_gallery(self, client):
        owner = make_user(username="landing_gallery_owner", email="landing_gallery_owner@example.com", handle="landing_gallery_owner")
        community = make_community("landing-gallery", creator=owner)
        challenge = CommunityChallenge.objects.create(
            community=community,
            title="Landing prompt",
            prompt_md="Prompt",
            starts_at=timezone.now() - timezone.timedelta(hours=1),
            ends_at=timezone.now() + timezone.timedelta(days=1),
            is_featured=True,
            created_by=owner,
        )
        Post.objects.create(
            community=community,
            author=owner,
            post_type="text",
            title="Challenge entry thread",
            body_md="Entry",
            score=5,
            hot_score=5,
            challenge=challenge,
        )

        response = client.get(reverse("community_landing", kwargs={"slug": community.slug}))

        assert response.status_code == 200
        assert "Challenge gallery" in response.content.decode()
        assert "Challenge entry thread" in response.content.decode()

    def test_owner_dashboard_requires_owner_or_staff(self, client):
        owner = make_user(username="owner_dash_owner", email="owner_dash_owner@example.com", handle="owner_dash_owner")
        moderator = make_user(username="owner_dash_mod", email="owner_dash_mod@example.com", handle="owner_dash_mod", mfa_totp_enabled=True)
        community = make_community("owner-dash-denied", creator=owner)
        CommunityMembership.objects.create(user=owner, community=community, role=CommunityMembership.Role.OWNER)
        CommunityMembership.objects.create(user=moderator, community=community, role=CommunityMembership.Role.MODERATOR)
        client.force_login(moderator)

        response = client.get(reverse("community_owner_dashboard", kwargs={"slug": community.slug}))

        assert response.status_code == 403
        assert "Owner access required" in response.content.decode()

    def test_owner_dashboard_renders_growth_health_and_threads(self, client):
        owner = make_user(username="owner_dash_ok", email="owner_dash_ok@example.com", handle="owner_dash_ok", mfa_totp_enabled=True)
        member = make_user(username="owner_dash_member", email="owner_dash_member@example.com", handle="owner_dash_member")
        community = make_community("owner-dash-ok", creator=owner)
        CommunityMembership.objects.create(user=owner, community=community, role=CommunityMembership.Role.OWNER)
        CommunityMembership.objects.create(user=member, community=community, role=CommunityMembership.Role.MEMBER)
        challenge = CommunityChallenge.objects.create(
            community=community,
            title="Owner dash prompt",
            prompt_md="Prompt",
            starts_at=timezone.now() - timezone.timedelta(hours=1),
            ends_at=timezone.now() + timezone.timedelta(days=3),
            is_featured=True,
            created_by=owner,
        )
        challenge.participations.create(user=member)
        invite = CommunityInvite.objects.create(community=community, created_by=owner, token="owner-dash-token", usage_count=2)
        post = Post.objects.create(
            community=community,
            author=member,
            post_type="text",
            title="Needs a reply",
            body_md="Body",
            challenge=challenge,
        )
        ModQueueItem.objects.create(
            community=community,
            post=post,
            content_type=ModQueueItem.ContentType.POST,
            status=ModQueueItem.Status.NEEDS_REVIEW,
        )
        client.force_login(owner)

        response = client.get(reverse("community_owner_dashboard", kwargs={"slug": community.slug}))

        assert response.status_code == 200
        content = response.content.decode()
        assert "How c/owner-dash-ok is moving this week" in content
        assert "Invite conversions" in content
        assert "Needs a reply" in content
        assert str(invite.usage_count) in content
