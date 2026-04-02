from __future__ import annotations

from dataclasses import dataclass

from apps.communities.models import CommunityMembership
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


@dataclass
class ReferralCommunityCard:
    community: object
    invite: object
    share_links: dict
    usage_count: int
    member_count: int


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


def onboarding_progress_for_user(user: User):
    joined_count = CommunityMembership.objects.filter(user=user).count()
    has_profile = bool((user.display_name or "").strip() or (user.bio or "").strip())
    has_post = Post.objects.filter(author=user).exists()
    has_comment = Comment.objects.filter(author=user).exists()
    has_referral = user.community_invites.filter(usage_count__gt=0).exists()
    return {
        "has_profile": has_profile,
        "joined_count": joined_count,
        "community_goal_done": joined_count >= 3,
        "has_post": has_post,
        "has_comment": has_comment,
        "has_referral": has_referral,
        "completed_steps": sum(
            [
                has_profile,
                joined_count >= 3,
                has_post or has_comment,
                has_referral,
            ]
        ),
        "total_steps": 4,
    }
