from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone

from apps.communities.models import CommunityChallengeParticipation, CommunityMembership
from apps.communities.services import create_invite_for_community, share_links_for_invite
from apps.posts.models import Comment, Post

from .models import User, UserBadge

BADGE_META = {
    UserBadge.BadgeCode.PROFILE_READY: {
        "title": "Profile Ready",
        "description": "Added a display name or bio so your account feels human from day one.",
        "icon": "✦",
    },
    UserBadge.BadgeCode.FIRST_STEPS: {
        "title": "First Steps",
        "description": "Completed the getting-started flow and picked your first communities.",
        "icon": "➜",
    },
    UserBadge.BadgeCode.FIRST_POST: {
        "title": "First Post",
        "description": "Published your first thread.",
        "icon": "✎",
    },
    UserBadge.BadgeCode.FIRST_COMMENT: {
        "title": "First Comment",
        "description": "Joined the conversation with your first comment.",
        "icon": "💬",
    },
    UserBadge.BadgeCode.FIRST_REFERRAL: {
        "title": "First Referral",
        "description": "Brought your first person into one of your communities.",
        "icon": "↗",
    },
    UserBadge.BadgeCode.CREW_BUILDER: {
        "title": "Crew Builder",
        "description": "Referred three new joins across your invite links.",
        "icon": "⚑",
    },
    UserBadge.BadgeCode.CHALLENGE_ACCEPTED: {
        "title": "Challenge Accepted",
        "description": "Joined your first community challenge.",
        "icon": "⚡",
    },
    UserBadge.BadgeCode.MOMENTUM: {
        "title": "Momentum",
        "description": "Stacked multiple engagement milestones and kept the energy going.",
        "icon": "▲",
    },
}


def award_badge(user: User, code: str):
    meta = BADGE_META[code]
    badge, _ = UserBadge.objects.get_or_create(
        user=user,
        code=code,
        defaults={
            "title": meta["title"],
            "description": meta["description"],
            "icon": meta["icon"],
        },
    )
    return badge


def award_profile_badges(user: User):
    if user.display_name.strip() or user.bio.strip():
        award_badge(user, UserBadge.BadgeCode.PROFILE_READY)


def award_onboarding_badges(user: User):
    if user.onboarding_completed:
        award_badge(user, UserBadge.BadgeCode.FIRST_STEPS)
    award_profile_badges(user)


def award_post_badges(user: User):
    if Post.objects.filter(author=user).exists():
        award_badge(user, UserBadge.BadgeCode.FIRST_POST)


def award_comment_badges(user: User):
    if Comment.objects.filter(author=user).exists():
        award_badge(user, UserBadge.BadgeCode.FIRST_COMMENT)


def award_referral_badges(user: User):
    total_referrals = sum(invite.usage_count for invite in user.community_invites.filter(is_active=True))
    if total_referrals >= 1:
        award_badge(user, UserBadge.BadgeCode.FIRST_REFERRAL)
    if total_referrals >= 3:
        award_badge(user, UserBadge.BadgeCode.CREW_BUILDER)
    award_momentum_badge(user)


def award_challenge_badges(user: User):
    total_participations = CommunityChallengeParticipation.objects.filter(user=user).count()
    if total_participations >= 1:
        award_badge(user, UserBadge.BadgeCode.CHALLENGE_ACCEPTED)
    award_momentum_badge(user)


def award_momentum_badge(user: User):
    earned_codes = set(user.badges.values_list("code", flat=True))
    anchor_codes = {
        UserBadge.BadgeCode.FIRST_STEPS,
        UserBadge.BadgeCode.FIRST_POST,
        UserBadge.BadgeCode.FIRST_COMMENT,
        UserBadge.BadgeCode.FIRST_REFERRAL,
        UserBadge.BadgeCode.CHALLENGE_ACCEPTED,
    }
    if len(earned_codes & anchor_codes) >= 3:
        award_badge(user, UserBadge.BadgeCode.MOMENTUM)


@dataclass
class ReferralCommunityCard:
    community: object
    invite: object
    share_links: dict
    usage_count: int
    member_count: int


@dataclass
class FirstWeekMission:
    key: str
    title: str
    detail: str
    completed: bool
    action_url: str
    action_label: str


def referral_cards_for_user(user: User, limit: int = 6):
    memberships = (
        CommunityMembership.objects.filter(user=user)
        .select_related("community")
        .order_by("-community__subscriber_count", "community__title")[:limit]
    )
    cards = []
    for membership in memberships:
        invite = create_invite_for_community(membership.community, user)
        cards.append(
            ReferralCommunityCard(
                community=membership.community,
                invite=invite,
                share_links=share_links_for_invite(membership.community, invite),
                usage_count=invite.usage_count,
                member_count=membership.community.subscriber_count,
            )
        )
    return cards


def referral_summary_for_user(user: User):
    cards = referral_cards_for_user(user)
    total_invite_links = len(cards)
    total_referrals = sum(card.usage_count for card in cards)
    total_badges = user.badges.count()
    featured_card = None
    if cards:
        featured_card = max(
            cards,
            key=lambda card: (card.usage_count, card.member_count, card.community.slug),
        )
    return {
        "cards": cards,
        "total_invite_links": total_invite_links,
        "total_referrals": total_referrals,
        "total_badges": total_badges,
        "featured_card": featured_card,
    }


def record_post_share(user: User):
    if user.first_post_share_at is None:
        user.first_post_share_at = timezone.now()
        user.save(update_fields=["first_post_share_at"])
    award_momentum_badge(user)


def first_week_missions_for_user(user: User):
    progress = onboarding_progress_for_user(user)
    return [
        FirstWeekMission(
            key="profile",
            title="Polish your profile",
            detail="Add a display name or short bio so people know why you are here.",
            completed=progress["has_profile"],
            action_url=reverse("account_settings"),
            action_label="Edit profile",
        ),
        FirstWeekMission(
            key="communities",
            title="Join 3 communities",
            detail="Wake up your feed with a few rooms that match your interests.",
            completed=progress["community_goal_done"],
            action_url=reverse("community_discovery"),
            action_label="Browse communities",
        ),
        FirstWeekMission(
            key="comment",
            title="Leave your first comment",
            detail="Reply to a thread so your first conversation starts quickly.",
            completed=progress["has_comment"],
            action_url=reverse("home"),
            action_label="Find a thread",
        ),
        FirstWeekMission(
            key="share",
            title="Share one thread",
            detail="Pass along a thread you like so the loop grows beyond the app.",
            completed=progress["has_shared_post"],
            action_url=reverse("popular"),
            action_label="Pick a thread",
        ),
        FirstWeekMission(
            key="challenge",
            title="Join a challenge",
            detail="Challenges are the fastest way to meet people with the same taste.",
            completed=progress["has_challenge"],
            action_url=f"{reverse('home')}#featured-challenges",
            action_label="View challenges",
        ),
        FirstWeekMission(
            key="follow",
            title="Follow one person",
            detail="Turn the home feed into a social space with friend activity.",
            completed=progress["has_follow"],
            action_url=reverse("community_discovery"),
            action_label="Meet people",
        ),
    ]


def onboarding_progress_for_user(user: User):
    joined_count = CommunityMembership.objects.filter(user=user).count()
    has_profile = bool((user.display_name or "").strip() or (user.bio or "").strip())
    has_post = Post.objects.filter(author=user).exists()
    has_comment = Comment.objects.filter(author=user).exists()
    has_referral = user.community_invites.filter(usage_count__gt=0).exists()
    has_challenge = CommunityChallengeParticipation.objects.filter(user=user).exists()
    has_shared_post = user.first_post_share_at is not None
    has_follow = user.followed_users.exists()
    return {
        "has_profile": has_profile,
        "joined_count": joined_count,
        "community_goal_done": joined_count >= 3,
        "has_post": has_post,
        "has_comment": has_comment,
        "has_referral": has_referral,
        "has_challenge": has_challenge,
        "has_shared_post": has_shared_post,
        "has_follow": has_follow,
        "completed_steps": sum(
            [
                has_profile,
                joined_count >= 3,
                has_comment,
                has_shared_post,
                has_challenge,
                has_follow,
            ]
        ),
        "total_steps": 6,
    }
