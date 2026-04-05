import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.communities.models import (
    Community,
    CommunityChallenge,
    CommunityChallengeParticipation,
    CommunityInvite,
    CommunityMembership,
    CommunityRule,
    CommunityWikiPage,
    PostFlair,
    UserFlair,
)

User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "community_model_user"),
        "email": overrides.pop("email", "community_model_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "community_model_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="builders", creator=None, **overrides):
    creator = creator or make_user(username=f"{slug}_creator", email=f"{slug}_creator@example.com", handle=f"{slug}_creator")
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "Community model test",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestCommunityModel:
    def test_save_generates_slug_and_renders_markdown_fields(self):
        creator = make_user(username="modelcreator", email="modelcreator@example.com", handle="modelcreator")
        community = Community(
            name="Agora Builders",
            title="Agora Builders",
            description="desc",
            creator=creator,
            sidebar_md="## Sidebar",
            landing_intro_md="**Intro**",
            faq_md="### FAQ",
            best_of_md="- Best of",
        )

        community.save()

        assert community.slug == "agora-builders"
        assert "<h2>Sidebar</h2>" in community.sidebar_html
        assert "<strong>Intro</strong>" in community.landing_intro_html
        assert "<h3>FAQ</h3>" in community.faq_html
        assert "<li>Best of</li>" in community.best_of_html

    def test_str_returns_prefixed_slug(self):
        community = make_community("alpha")

        assert str(community) == "c/alpha"

    def test_default_posting_and_privacy_flags(self):
        community = make_community("defaults")

        assert community.community_type == Community.CommunityType.PUBLIC
        assert community.allow_text_posts is True
        assert community.allow_link_posts is True
        assert community.allow_image_posts is True
        assert community.allow_polls is False
        assert community.vote_hide_minutes == 60
        assert community.require_post_flair is False


@pytest.mark.django_db
class TestCommunityRelatedModels:
    def test_membership_unique_together_blocks_duplicates(self):
        user = make_user(username="member", email="member@example.com", handle="member")
        community = make_community("membership")
        CommunityMembership.objects.create(user=user, community=community, role=CommunityMembership.Role.MEMBER)

        with pytest.raises(IntegrityError):
            CommunityMembership.objects.create(user=user, community=community, role=CommunityMembership.Role.MEMBER)

    def test_rule_ordering_is_by_order_then_id(self):
        community = make_community("rules")
        later = CommunityRule.objects.create(community=community, order=2, title="Later")
        earlier = CommunityRule.objects.create(community=community, order=1, title="Earlier")

        assert list(CommunityRule.objects.values_list("id", flat=True))[:2] == [earlier.id, later.id]

    def test_userflair_unique_together_blocks_duplicates(self):
        community = make_community("userflair")
        user = make_user(username="flairuser", email="flairuser@example.com", handle="flairuser")
        UserFlair.objects.create(community=community, user=user, text="Builder")

        with pytest.raises(IntegrityError):
            UserFlair.objects.create(community=community, user=user, text="Duplicate")

    def test_wiki_page_save_renders_html_and_str(self):
        community = make_community("wiki")
        editor = make_user(username="wikieditor", email="wikieditor@example.com", handle="wikieditor")
        page = CommunityWikiPage.objects.create(
            community=community,
            slug="home",
            title="Home",
            body_md="## Welcome",
            updated_by=editor,
        )

        assert "<h2>Welcome</h2>" in page.body_html
        assert str(page) == "wiki:home"

    def test_wiki_page_unique_together_blocks_duplicate_slug_per_community(self):
        community = make_community("wikidup")
        CommunityWikiPage.objects.create(community=community, slug="home", title="Home")

        with pytest.raises(IntegrityError):
            CommunityWikiPage.objects.create(community=community, slug="home", title="Duplicate")

    def test_invite_str_and_defaults(self):
        community = make_community("invite")
        invite = CommunityInvite.objects.create(community=community, token="invite-token")

        assert str(invite) == "Invite invite-token for c/invite"
        assert invite.usage_count == 0
        assert invite.is_active is True

    def test_challenge_save_renders_html_and_is_active(self):
        community = make_community("challenge")
        now = timezone.now()
        challenge = CommunityChallenge.objects.create(
            community=community,
            title="Weekly Prompt",
            prompt_md="**Share** what you're building.",
            starts_at=now - timezone.timedelta(hours=1),
            ends_at=now + timezone.timedelta(hours=1),
        )

        assert "<strong>Share</strong>" in challenge.prompt_html
        assert challenge.is_active() is True

    def test_challenge_participation_unique_and_str(self):
        community = make_community("participation")
        user = make_user(username="participant", email="participant@example.com", handle="participant")
        challenge = CommunityChallenge.objects.create(
            community=community,
            title="Join me",
            prompt_md="Prompt",
            starts_at=timezone.now() - timezone.timedelta(days=1),
            ends_at=timezone.now() + timezone.timedelta(days=1),
        )
        participation = CommunityChallengeParticipation.objects.create(challenge=challenge, user=user)

        assert str(participation) == f"{user} joined {challenge.title}"
        with pytest.raises(IntegrityError):
            CommunityChallengeParticipation.objects.create(challenge=challenge, user=user)


@pytest.mark.django_db
class TestFlairModels:
    def test_postflair_can_be_created_with_defaults(self):
        community = make_community("postflair")
        flair = PostFlair.objects.create(community=community, text="Announcement")

        assert flair.bg_color == "#6B7280"
