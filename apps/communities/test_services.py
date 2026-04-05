from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone

from apps.accounts.models import Notification, UserBadge
from apps.communities.forms import CommunityWikiPageForm
from apps.communities.models import (
    Community,
    CommunityChallenge,
    CommunityChallengeParticipation,
    CommunityInvite,
    CommunityMembership,
)
from apps.communities.services import (
    active_challenge_for_community,
    best_posts_for_community,
    build_invite_url,
    can_join_community,
    can_participate_in_community,
    can_view_community,
    community_leaderboard,
    create_invite_for_community,
    enrich_challenges_for_user,
    featured_challenges_for_user,
    following_activity_for_user,
    join_challenge,
    notify_followers_about_join,
    redeem_invite,
    redeem_pending_invite_token,
    refresh_subscriber_count,
    save_wiki_page,
    send_friend_invites,
    share_links_for_challenge,
    share_links_for_invite,
    submit_community,
    suggested_communities_for_user,
    toggle_user_membership,
    user_membership_for_community,
)
from apps.posts.models import Comment, Post
from apps.votes.models import SavedPost, Vote


User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "community_service_user"),
        "email": overrides.pop("email", "community_service_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "community_service_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="service-community", creator=None, **overrides):
    creator = creator or make_user(username=f"{slug}_creator", email=f"{slug}_creator@example.com", handle=f"{slug}_creator")
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "Service tests",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestCommunityServices:
    def test_submit_community_assigns_owner_membership_and_subscriber_count(self):
        creator = make_user(username="submit_creator", email="submit_creator@example.com", handle="submit_creator")
        form = SimpleNamespace(
            save=lambda commit=False: Community(
                name="Submitted",
                slug="submitted",
                title="Submitted",
                description="Submitted",
            )
        )

        community = submit_community(creator, form)

        membership = CommunityMembership.objects.get(user=creator, community=community)
        assert membership.role == CommunityMembership.Role.OWNER
        assert community.subscriber_count == 1

    def test_refresh_subscriber_count_counts_memberships(self):
        community = make_community("refresh")
        CommunityMembership.objects.create(user=make_user(username="m1", email="m1@example.com", handle="m1"), community=community)
        CommunityMembership.objects.create(user=make_user(username="m2", email="m2@example.com", handle="m2"), community=community)

        refresh_subscriber_count(community)
        community.refresh_from_db()

        assert community.subscriber_count == 2

    def test_membership_and_visibility_helpers_cover_public_restricted_private(self):
        member = make_user(username="helpermember", email="helpermember@example.com", handle="helpermember")
        public = make_community("public-helper", community_type=Community.CommunityType.PUBLIC)
        restricted = make_community("restricted-helper", community_type=Community.CommunityType.RESTRICTED)
        private = make_community("private-helper", community_type=Community.CommunityType.PRIVATE)
        CommunityMembership.objects.create(user=member, community=private)
        CommunityMembership.objects.create(user=member, community=restricted)

        assert user_membership_for_community(None, public) is None
        assert can_view_community(None, public) is True
        assert can_view_community(None, private) is False
        assert can_view_community(member, private) is True
        assert can_join_community(member, public) is True
        assert can_join_community(member, restricted) is True
        outsider = make_user(username="outsider", email="outsider@example.com", handle="outsider")
        assert can_join_community(outsider, restricted) is False
        assert can_participate_in_community(outsider, public) is True
        assert can_participate_in_community(outsider, restricted) is False

    def test_toggle_user_membership_joins_then_leaves_and_rejects_owner_leave(self):
        user = make_user(username="togglemember", email="togglemember@example.com", handle="togglemember")
        community = make_community("toggle-membership")

        joined = toggle_user_membership(user, community)
        assert joined is True
        assert CommunityMembership.objects.filter(user=user, community=community).exists()

        left = toggle_user_membership(user, community)
        assert left is False
        assert not CommunityMembership.objects.filter(user=user, community=community).exists()

        owner = make_user(username="ownerleave", email="ownerleave@example.com", handle="ownerleave")
        CommunityMembership.objects.create(user=owner, community=community, role=CommunityMembership.Role.OWNER)
        with pytest.raises(ValueError):
            toggle_user_membership(owner, community)

    def test_save_wiki_page_assigns_community_and_editor(self):
        user = make_user(username="wikisaver", email="wikisaver@example.com", handle="wikisaver")
        community = make_community("save-wiki")
        form = CommunityWikiPageForm(data={"slug": "home", "title": "Home", "body_md": "## Welcome"})

        assert form.is_valid() is True
        page = save_wiki_page(user, community, form)

        assert page.community == community
        assert page.updated_by == user
        assert "<h2>Welcome</h2>" in page.body_html

    def test_create_invite_is_idempotent_for_same_community_and_creator(self):
        user = make_user(username="inviter", email="inviter@example.com", handle="inviter")
        community = make_community("idempotent-invite")

        first = create_invite_for_community(community, user)
        second = create_invite_for_community(community, user)

        assert first.id == second.id
        assert first.token

    def test_build_invite_url_supports_relative_and_public_base_url(self, settings):
        community = make_community("invite-url")
        invite = CommunityInvite.objects.create(community=community, token="abc123")

        settings.APP_PUBLIC_URL = ""
        assert build_invite_url(community, invite) == f"/c/{community.slug}/invite/{invite.token}/"

        settings.APP_PUBLIC_URL = "https://aggora.example"
        assert build_invite_url(community, invite) == f"https://aggora.example/c/{community.slug}/invite/{invite.token}/"

    def test_redeem_invite_increments_usage_only_once_and_awards_referral_badge(self):
        creator = make_user(username="referrer", email="referrer@example.com", handle="referrer")
        joiner = make_user(username="joiner_service", email="joiner_service@example.com", handle="joiner_service")
        community = make_community("redeem-invite", creator=creator)
        invite = CommunityInvite.objects.create(community=community, created_by=creator, token="redeemtoken")

        redeemed = redeem_invite(joiner, invite)
        invite.refresh_from_db()
        assert redeemed == community
        assert invite.usage_count == 1
        assert UserBadge.objects.filter(user=creator, code=UserBadge.BadgeCode.FIRST_REFERRAL).exists()

        redeem_invite(joiner, invite)
        invite.refresh_from_db()
        assert invite.usage_count == 1

    def test_redeem_pending_invite_returns_none_for_missing_token(self):
        user = make_user(username="pendingnone", email="pendingnone@example.com", handle="pendingnone")

        assert redeem_pending_invite_token(user, None) is None
        assert redeem_pending_invite_token(user, "missing") is None

    def test_send_friend_invites_sends_email(self, settings):
        settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
        settings.APP_NAME = "Agora"
        sender = make_user(username="sender", email="sender@example.com", handle="sender")
        community = make_community("mail-invite", creator=sender)
        invite = CommunityInvite.objects.create(community=community, created_by=sender, token="mailtoken")

        send_friend_invites(sender, community, invite, ["friend@example.com"])

        assert len(mail.outbox) == 1
        assert "invited you to c/mail-invite on Agora" in mail.outbox[0].subject
        assert "friend@example.com" in mail.outbox[0].to

    def test_suggested_communities_uses_follow_vote_and_save_signals(self):
        user = make_user(username="suggested", email="suggested@example.com", handle="suggested")
        followed = make_user(username="followed", email="followed@example.com", handle="followed")
        user.followed_users.add(followed)
        community = make_community("signal-community")
        CommunityMembership.objects.create(user=followed, community=community)
        post = Post.objects.create(community=community, author=followed, post_type="text", title="Signal", body_md="Body")
        Vote.objects.create(user=user, post=post, value=Vote.VoteType.UPVOTE)
        SavedPost.objects.create(user=user, post=post)

        suggestions = suggested_communities_for_user(user)

        assert suggestions[0] == community

    def test_community_leaderboard_aggregates_posts_and_comments(self):
        author = make_user(username="leader", email="leader@example.com", handle="leader")
        community = make_community("leaderboard", creator=author)
        post = Post.objects.create(community=community, author=author, post_type="text", title="Top", body_md="Body", score=6, hot_score=6)
        Comment.objects.create(post=post, author=author, body_md="Comment", body_html="<p>Comment</p>", score=4)

        leaderboard = community_leaderboard(community)

        assert leaderboard[0]["user"] == author
        assert leaderboard[0]["total_points"] == 10
        assert leaderboard[0]["posts"] == 1
        assert leaderboard[0]["comments"] == 1

    def test_challenge_helpers_return_active_featured_and_best_posts(self):
        user = make_user(username="challengeuser", email="challengeuser@example.com", handle="challengeuser")
        community = make_community("challenge-helpers", creator=user)
        now = timezone.now()
        active = CommunityChallenge.objects.create(
            community=community,
            title="Active",
            prompt_md="Prompt",
            starts_at=now - timezone.timedelta(hours=1),
            ends_at=now + timezone.timedelta(hours=2),
            is_featured=True,
        )
        Post.objects.create(community=community, author=user, post_type="text", title="Best", body_md="Body", score=9, hot_score=9)

        assert active_challenge_for_community(community) == active
        assert featured_challenges_for_user(None)
        assert best_posts_for_community(community)[0].title == "Best"

    def test_notify_followers_about_join_skips_disabled_and_deduplicates_recent_entries(self):
        actor = make_user(username="joinactor", email="joinactor@example.com", handle="joinactor")
        follower = make_user(username="follower", email="follower@example.com", handle="follower")
        muted = make_user(username="muted", email="muted@example.com", handle="muted", notify_on_follows=False)
        actor.followers.add(follower, muted)
        community = make_community("notify-join", creator=actor)

        notify_followers_about_join(actor, community)
        notify_followers_about_join(actor, community)

        assert Notification.objects.filter(user=follower, actor=actor, community=community).count() == 1
        assert Notification.objects.filter(user=muted, actor=actor, community=community).count() == 0

    def test_share_link_builders_include_copy_url_and_channel_links(self, settings):
        settings.APP_NAME = "Agora"
        settings.APP_PUBLIC_URL = "https://aggora.example"
        creator = make_user(username="sharecreator", email="sharecreator@example.com", handle="sharecreator")
        community = make_community("share-links", creator=creator)
        invite = CommunityInvite.objects.create(community=community, token="sharetoken")
        challenge = CommunityChallenge.objects.create(
            community=community,
            title="Ship Week",
            prompt_md="Prompt",
            starts_at=timezone.now() - timezone.timedelta(hours=1),
            ends_at=timezone.now() + timezone.timedelta(hours=2),
        )

        invite_links = share_links_for_invite(community, invite)
        challenge_links = share_links_for_challenge(challenge)

        assert invite_links["copy_url"].endswith(f"/c/{community.slug}/invite/{invite.token}/")
        assert "wa.me" in invite_links["whatsapp"]
        assert "twitter.com" in challenge_links["x"]
        assert challenge_links["copy_url"].endswith(f"/c/{community.slug}/landing/")

    def test_join_challenge_creates_participation_and_awards_badge(self):
        user = make_user(username="joinchallenge", email="joinchallenge@example.com", handle="joinchallenge")
        community = make_community("join-challenge", creator=user)
        challenge = CommunityChallenge.objects.create(
            community=community,
            title="Join",
            prompt_md="Prompt",
            starts_at=timezone.now() - timezone.timedelta(hours=1),
            ends_at=timezone.now() + timezone.timedelta(hours=2),
        )

        participation, created = join_challenge(user, challenge)

        assert created is True
        assert CommunityChallengeParticipation.objects.filter(pk=participation.pk).exists()
        assert UserBadge.objects.filter(user=user, code=UserBadge.BadgeCode.CHALLENGE_ACCEPTED).exists()

    def test_enrich_challenges_for_user_adds_join_state_participants_and_share_links(self):
        user = make_user(username="enrich", email="enrich@example.com", handle="enrich")
        community = make_community("enrich-community", creator=user)
        challenge = CommunityChallenge.objects.create(
            community=community,
            title="Enrich",
            prompt_md="Prompt",
            starts_at=timezone.now() - timezone.timedelta(hours=1),
            ends_at=timezone.now() + timezone.timedelta(hours=2),
        )
        CommunityChallengeParticipation.objects.create(challenge=challenge, user=user)

        enriched = enrich_challenges_for_user([challenge], user)[0]

        assert enriched.participant_count == 1
        assert enriched.is_joined is True
        assert "copy_url" in enriched.share_links

    def test_following_activity_collects_post_comment_and_join_events(self):
        viewer = make_user(username="viewer_activity", email="viewer_activity@example.com", handle="viewer_activity")
        actor = make_user(username="actor_activity", email="actor_activity@example.com", handle="actor_activity")
        viewer.followed_users.add(actor)
        community = make_community("activity", creator=actor)
        CommunityMembership.objects.create(user=actor, community=community)
        post = Post.objects.create(community=community, author=actor, post_type="text", title="Posted", body_md="Body", score=2, hot_score=2)
        Comment.objects.create(post=post, author=actor, body_md="Reply", body_html="<p>Reply</p>")

        items = following_activity_for_user(viewer)

        kinds = {item.kind for item in items}
        assert {"post", "comment", "join"} <= kinds
