from __future__ import annotations

import secrets
from collections import Counter, defaultdict
from dataclasses import dataclass
from urllib.parse import quote_plus

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.posts.models import Comment, Post
from apps.votes.models import SavedPost, Vote

from .models import (
    Community,
    CommunityChallenge,
    CommunityChallengeParticipation,
    CommunityInvite,
    CommunityMembership,
    CommunityWikiPage,
)


def submit_community(creator: User, form) -> Community:
    """Service to create a new community and assign the owner role."""
    community = form.save(commit=False)
    community.creator = creator
    community.save()
    
    CommunityMembership.objects.create(
        user=creator,
        community=community,
        role=CommunityMembership.Role.OWNER,
    )
    community.subscriber_count = community.memberships.count()
    community.save(update_fields=["subscriber_count"])
    return community


def refresh_subscriber_count(community: Community):
    community.subscriber_count = community.memberships.count()
    community.save(update_fields=["subscriber_count"])


def user_membership_for_community(user: User | None, community: Community):
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return CommunityMembership.objects.filter(user=user, community=community).first()


def can_view_community(user: User | None, community: Community) -> bool:
    if community.community_type != Community.CommunityType.PRIVATE:
        return True
    return user_membership_for_community(user, community) is not None


def can_join_community(user: User, community: Community) -> bool:
    membership = user_membership_for_community(user, community)
    if membership is not None:
        return True
    return community.community_type == Community.CommunityType.PUBLIC


def can_participate_in_community(user: User, community: Community) -> bool:
    if community.community_type == Community.CommunityType.PUBLIC:
        return True
    return user_membership_for_community(user, community) is not None


def toggle_user_membership(user: User, community: Community) -> bool:
    """
    Toggles membership for a user in a community.
    Returns: bool - True if the user successfully joined, False if they successfully left.
    Raises: ValueError if the owner attempts to leave.
    """
    membership, created = CommunityMembership.objects.get_or_create(
        user=user,
        community=community,
        defaults={"role": CommunityMembership.Role.MEMBER},
    )
    if not created:
        if membership.role == CommunityMembership.Role.OWNER:
            raise ValueError("Owners cannot leave their own community.")
        membership.delete()
        joined = False
    else:
        joined = True

    refresh_subscriber_count(community)
    if joined:
        notify_followers_about_join(user, community)
    return joined


def save_wiki_page(user: User, community: Community, form) -> CommunityWikiPage:
    """Saves a community Wiki page and records the updater."""
    page = form.save(commit=False)
    page.community = community
    page.updated_by = user
    page.save()
    return page


def create_invite_for_community(community: Community, user: User | None = None) -> CommunityInvite:
    invite, created = CommunityInvite.objects.get_or_create(
        community=community,
        created_by=user,
        is_active=True,
        defaults={"token": secrets.token_urlsafe(12)[:24]},
    )
    if not created and not invite.token:
        invite.token = secrets.token_urlsafe(12)[:24]
        invite.save(update_fields=["token"])
    return invite


def build_invite_url(community: Community, invite: CommunityInvite) -> str:
    base_url = getattr(settings, "APP_PUBLIC_URL", "").rstrip("/")
    path = reverse("community_invite", kwargs={"slug": community.slug, "token": invite.token})
    if base_url:
        return f"{base_url}{path}"
    return path


def redeem_invite(user: User, invite: CommunityInvite) -> Community:
    was_member = CommunityMembership.objects.filter(user=user, community=invite.community).exists()
    CommunityMembership.objects.get_or_create(
        user=user,
        community=invite.community,
        defaults={"role": CommunityMembership.Role.MEMBER},
    )
    if not was_member:
        invite.usage_count += 1
        invite.save(update_fields=["usage_count"])
        if invite.created_by_id and invite.created_by_id != user.id:
            from apps.accounts.growth import award_referral_badges

            award_referral_badges(invite.created_by)
    refresh_subscriber_count(invite.community)
    notify_followers_about_join(user, invite.community)
    return invite.community


def redeem_pending_invite_token(user: User, token: str | None):
    if not token:
        return None
    invite = CommunityInvite.objects.filter(token=token, is_active=True).select_related("community").first()
    if not invite:
        return None
    return redeem_invite(user, invite)


def send_friend_invites(sender: User, community: Community, invite: CommunityInvite, recipient_emails: list[str]):
    invite_url = build_invite_url(community, invite)
    sender_name = sender.display_name or sender.handle or sender.email
    subject = f"{sender_name} invited you to c/{community.slug} on {settings.APP_NAME}"
    message = (
        f"{sender_name} invited you to join c/{community.slug} on {settings.APP_NAME}.\n\n"
        f"Join here: {invite_url}\n\n"
        "You'll land on a page that lets you join and publish your first post in one flow."
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_emails,
        fail_silently=True,
    )


def suggested_communities_for_user(user: User, limit: int = 6):
    base_queryset = Community.objects.all().select_related("creator")
    if user is None or not user.is_authenticated:
        return list(base_queryset.order_by("-subscriber_count", "-created_at")[:limit])

    joined_ids = set(user.communitymembership_set.values_list("community_id", flat=True))
    scores = Counter()

    followed_ids = list(user.followed_users.values_list("id", flat=True))
    if followed_ids:
        for community_id in CommunityMembership.objects.filter(user_id__in=followed_ids).values_list("community_id", flat=True):
            if community_id not in joined_ids:
                scores[community_id] += 4

    interacted_ids = list(
        Vote.objects.filter(user=user, post__isnull=False)
        .exclude(post__community_id__in=joined_ids)
        .values_list("post__community_id", flat=True)
    )
    for community_id in interacted_ids:
        scores[community_id] += 2

    saved_ids = list(
        SavedPost.objects.filter(user=user)
        .exclude(post__community_id__in=joined_ids)
        .values_list("post__community_id", flat=True)
    )
    for community_id in saved_ids:
        scores[community_id] += 3

    if scores:
        ordered_ids = [community_id for community_id, _ in scores.most_common(limit * 2)]
        communities_by_id = {community.id: community for community in base_queryset.filter(id__in=ordered_ids)}
        ordered = [communities_by_id[community_id] for community_id in ordered_ids if community_id in communities_by_id]
        return ordered[:limit]

    queryset = base_queryset.exclude(id__in=joined_ids).order_by("-subscriber_count", "-created_at")
    return list(queryset[:limit])


def community_leaderboard(community: Community, days: int = 7, limit: int = 5):
    since = timezone.now() - timezone.timedelta(days=days)
    scores = defaultdict(lambda: {"user": None, "post_points": 0, "comment_points": 0, "posts": 0, "comments": 0})

    recent_posts = Post.objects.filter(community=community, created_at__gte=since, is_removed=False).select_related("author")
    for post in recent_posts:
        if not post.author_id:
            continue
        entry = scores[post.author_id]
        entry["user"] = post.author
        entry["post_points"] += max(post.score, 0)
        entry["posts"] += 1

    recent_comments = Comment.objects.filter(post__community=community, created_at__gte=since, is_removed=False).select_related("author")
    for comment in recent_comments:
        if not comment.author_id:
            continue
        entry = scores[comment.author_id]
        entry["user"] = comment.author
        entry["comment_points"] += max(comment.score, 0)
        entry["comments"] += 1

    leaderboard = []
    for entry in scores.values():
        total_points = entry["post_points"] + entry["comment_points"]
        leaderboard.append(
            {
                "user": entry["user"],
                "total_points": total_points,
                "post_points": entry["post_points"],
                "comment_points": entry["comment_points"],
                "posts": entry["posts"],
                "comments": entry["comments"],
            }
        )
    leaderboard.sort(key=lambda item: (-item["total_points"], -(item["posts"] + item["comments"]), item["user"].handle or ""))
    return leaderboard[:limit]


def active_challenge_for_community(community: Community):
    now = timezone.now()
    return (
        community.challenges.filter(starts_at__lte=now, ends_at__gte=now, is_featured=True)
        .order_by("ends_at", "-created_at")
        .first()
    )


def featured_challenges_for_user(user: User, limit: int = 3):
    now = timezone.now()
    queryset = CommunityChallenge.objects.filter(starts_at__lte=now, ends_at__gte=now, is_featured=True).select_related("community")
    if user is not None and user.is_authenticated:
        joined_ids = list(user.communitymembership_set.values_list("community_id", flat=True))
        if joined_ids:
            queryset = queryset.filter(community_id__in=joined_ids)
    challenges = list(queryset.order_by("ends_at", "-created_at")[:limit])
    return enrich_challenges_for_user(challenges, user)


def best_posts_for_community(community: Community, limit: int = 5):
    return list(
        Post.objects.visible()
        .for_listing()
        .filter(community=community)
        .order_by("-score", "-comment_count", "-created_at")[:limit]
    )


def notify_followers_about_join(user: User, community: Community):
    from apps.accounts.models import Notification

    followers = list(user.followers.exclude(pk=user.pk))
    if not followers:
        return
    url = reverse("community_detail", kwargs={"slug": community.slug})
    for follower in followers:
        if not follower.notify_on_follows:
            continue
        if Notification.objects.filter(
            user=follower,
            actor=user,
            community=community,
            notification_type=Notification.NotificationType.FOLLOWED_USER_JOINED,
            created_at__gte=timezone.now() - timezone.timedelta(hours=12),
        ).exists():
            continue
        Notification.objects.create(
            user=follower,
            actor=user,
            community=community,
            notification_type=Notification.NotificationType.FOLLOWED_USER_JOINED,
            message=f"{user.handle or user.email} joined c/{community.slug}",
            url=url,
        )


def share_links_for_invite(community: Community, invite: CommunityInvite):
    invite_url = build_invite_url(community, invite)
    share_message = f"Join me in c/{community.slug} on {settings.APP_NAME} and publish your first post."
    share_text = quote_plus(share_message)
    encoded_url = quote_plus(invite_url)
    return {
        "copy_url": invite_url,
        "share_text": share_message,
        "whatsapp": f"https://wa.me/?text={share_text}%20{encoded_url}",
        "telegram": f"https://t.me/share/url?url={encoded_url}&text={share_text}",
        "x": f"https://twitter.com/intent/tweet?text={share_text}&url={encoded_url}",
        "email": f"mailto:?subject={quote_plus(f'Join me on {settings.APP_NAME}')}&body={quote_plus(f'{share_message}\n\n{invite_url}')}",
    }


def share_links_for_challenge(challenge: CommunityChallenge):
    base_url = getattr(settings, "APP_PUBLIC_URL", "").rstrip("/")
    path = reverse("community_landing", kwargs={"slug": challenge.community.slug})
    landing_url = f"{base_url}{path}" if base_url else path
    share_message = challenge.share_text or f"Jump into the {challenge.title} challenge in c/{challenge.community.slug}."
    encoded_url = quote_plus(landing_url)
    encoded_text = quote_plus(share_message)
    return {
        "copy_url": landing_url,
        "share_text": share_message,
        "whatsapp": f"https://wa.me/?text={encoded_text}%20{encoded_url}",
        "telegram": f"https://t.me/share/url?url={encoded_url}&text={encoded_text}",
        "x": f"https://twitter.com/intent/tweet?text={encoded_text}&url={encoded_url}",
        "email": f"mailto:?subject={quote_plus(challenge.title)}&body={quote_plus(f'{share_message}\n\n{landing_url}')}",
    }


def join_challenge(user: User, challenge: CommunityChallenge):
    participation, created = CommunityChallengeParticipation.objects.get_or_create(user=user, challenge=challenge)
    if created:
        from apps.accounts.growth import award_challenge_badges

        award_challenge_badges(user)
    return participation, created


def enrich_challenges_for_user(challenges, user: User | None):
    challenge_ids = [challenge.id for challenge in challenges]
    if not challenge_ids:
        return []
    participant_rows = (
        CommunityChallengeParticipation.objects.filter(challenge_id__in=challenge_ids)
        .values("challenge_id")
        .annotate(count=Count("id"))
    )
    participant_counts = {row["challenge_id"]: row["count"] for row in participant_rows}
    joined_ids = set()
    if user is not None and getattr(user, "is_authenticated", False):
        joined_ids = set(
            CommunityChallengeParticipation.objects.filter(user=user, challenge_id__in=challenge_ids).values_list(
                "challenge_id",
                flat=True,
            )
        )
    for challenge in challenges:
        challenge.participant_count = participant_counts.get(challenge.id, 0)
        challenge.is_joined = challenge.id in joined_ids
        challenge.share_links = share_links_for_challenge(challenge)
    return challenges


@dataclass
class FollowingActivityItem:
    actor: User
    kind: str
    label: str
    detail: str
    url: str
    created_at: object


def following_activity_for_user(user: User | None, limit: int = 6):
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    followed_ids = list(user.followed_users.values_list("id", flat=True))
    if not followed_ids:
        return []

    items = []

    recent_posts = (
        Post.objects.visible()
        .for_listing()
        .filter(author_id__in=followed_ids)
        .select_related("community", "author")
        .order_by("-created_at")[: limit * 3]
    )
    for post in recent_posts:
        if can_view_community(user, post.community):
            items.append(
                FollowingActivityItem(
                    actor=post.author,
                    kind="post",
                    label=f"{post.author.display_name or post.author.handle} posted",
                    detail=f"{post.title} in c/{post.community.slug}",
                    url=reverse(
                        "post_detail",
                        kwargs={"community_slug": post.community.slug, "post_id": post.id, "slug": post.slug},
                    ),
                    created_at=post.created_at,
                )
            )

    recent_comments = (
        Comment.objects.filter(author_id__in=followed_ids, is_removed=False)
        .select_related("author", "post", "post__community")
        .order_by("-created_at")[: limit * 3]
    )
    for comment in recent_comments:
        if can_view_community(user, comment.post.community):
            items.append(
                FollowingActivityItem(
                    actor=comment.author,
                    kind="comment",
                    label=f"{comment.author.display_name or comment.author.handle} replied",
                    detail=f"In {comment.post.title}",
                    url=reverse(
                        "post_detail",
                        kwargs={
                            "community_slug": comment.post.community.slug,
                            "post_id": comment.post.id,
                            "slug": comment.post.slug,
                        },
                    ),
                    created_at=comment.created_at,
                )
            )

    recent_joins = (
        CommunityMembership.objects.filter(user_id__in=followed_ids)
        .select_related("user", "community")
        .order_by("-joined_at")[: limit * 3]
    )
    for membership in recent_joins:
        if can_view_community(user, membership.community):
            items.append(
                FollowingActivityItem(
                    actor=membership.user,
                    kind="join",
                    label=f"{membership.user.display_name or membership.user.handle} joined",
                    detail=f"c/{membership.community.slug}",
                    url=reverse("community_detail", kwargs={"slug": membership.community.slug}),
                    created_at=membership.joined_at,
                )
            )

    items.sort(key=lambda item: item.created_at, reverse=True)
    return items[:limit]
