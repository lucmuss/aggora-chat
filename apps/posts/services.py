from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import quote_plus

from django.conf import settings
from django.db import models
from django.db.models import Count, Max
from django.db.models import Case, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone as django_timezone

from apps.accounts.mentions import resolve_mentioned_users
from apps.accounts.models import Notification
from apps.common.celery import dispatch_task
from apps.communities.models import Community, CommunityChallenge
from apps.search.tasks import index_post_task
from apps.votes.models import SavedPost, Vote
from apps.votes.tasks import recalculate_post_vote_totals

from .models import Comment, Poll, PollOption, PollVote, Post

EPOCH = datetime(2005, 12, 8, 7, 46, 43, tzinfo=timezone.utc)
POST_SORT_MAP = {
    "hot": ["-hot_score", "-created_at"],
    "new": ["-created_at"],
    "top": ["-score", "-created_at"],
    "rising": ["-upvote_count", "-created_at"],
}


def hot_score(ups: int, downs: int, created_at) -> float:
    score = ups - downs
    order = math.log10(max(abs(score), 1))
    sign = 1 if score > 0 else -1 if score < 0 else 0
    seconds = (created_at - EPOCH).total_seconds()
    return round(sign * order + seconds / 45000, 7)


def submit_post(user, community, post_data: dict, poll_lines: list[str] = None, crosspost_source_id: str = None) -> Post:
    """Service to create a post and handle related side effects like upvoting and indexing."""
    post = Post(
        author=user,
        community=community,
        title=post_data["title"],
        body_md=post_data.get("body_md", ""),
        post_type=post_data["post_type"],
        url=post_data.get("url", ""),
        image=post_data.get("image"),
        flair=post_data.get("flair"),
        challenge=post_data.get("challenge"),
        is_spoiler=post_data.get("is_spoiler", False),
        is_nsfw=post_data.get("is_nsfw", False),
        is_locked=post_data.get("is_locked", False),
        is_stickied=post_data.get("is_stickied", False),
    )
    if post.post_type == Post.PostType.CROSSPOST and crosspost_source_id:
        post.crosspost_parent = get_object_or_404(Post.objects.visible(), pk=crosspost_source_id)

    post.save()

    if post.post_type == Post.PostType.POLL and poll_lines:
        poll = Poll.objects.create(post=post)
        for index, label in enumerate(poll_lines, start=1):
            PollOption.objects.create(poll=poll, label=label, position=index)

    # Initial self-upvote
    Vote.objects.create(user=user, post=post, value=Vote.VoteType.UPVOTE)
    post.upvote_count = 1
    post.score = 1
    post.hot_score = hot_score(1, 0, post.created_at)
    post.save(update_fields=["upvote_count", "score", "hot_score", "body_html"])
    from apps.accounts.growth import award_post_badges

    award_post_badges(user)
    create_mention_notifications(post=post, actor=user, text_chunks=[post.title, post.body_md])
    dispatch_task(index_post_task, post.pk)
    return post


def submit_comment(user, post: Post, body_md: str, parent_id: str | None = None) -> Comment:
    """Service to create a comment and handle vote/counter side effects."""
    parent = None
    depth = 0
    if parent_id:
        parent = get_object_or_404(Comment, pk=parent_id, post=post)
        depth = parent.depth + 1
        if depth > 10:
            raise ValueError("Maximum nesting depth reached.")

    comment = Comment.objects.create(post=post, parent=parent, author=user, body_md=body_md, depth=depth)
    Vote.objects.create(user=user, comment=comment, value=Vote.VoteType.UPVOTE)
    comment.upvote_count = 1
    comment.score = 1
    comment.save(update_fields=["upvote_count", "score", "body_html"])

    Post.objects.filter(pk=post.pk).update(comment_count=models.F("comment_count") + 1)
    dispatch_task(recalculate_post_vote_totals, post.id)
    create_reengagement_notifications(comment)
    create_mention_notifications(comment=comment, post=post, actor=user, text_chunks=[comment.body_md])
    from apps.accounts.growth import award_comment_badges

    award_comment_badges(user)
    return comment


def create_mention_notifications(*, actor, text_chunks: list[str], post: Post, comment: Comment | None = None):
    mentioned_users = resolve_mentioned_users(*text_chunks, exclude_ids=[actor.id])
    if not mentioned_users.exists():
        return
    target_url = reverse(
        "post_detail",
        kwargs={"community_slug": post.community.slug, "post_id": post.id, "slug": post.slug},
    )
    if comment is not None:
        target_url = f"{target_url}#comment-{comment.id}"
        message = f"{actor.handle or actor.username} mentioned you in a comment."
    else:
        message = f"{actor.handle or actor.username} mentioned you in a thread."

    notifications = []
    for mentioned_user in mentioned_users:
        notifications.append(
            Notification(
                user=mentioned_user,
                actor=actor,
                community=post.community,
                post=post,
                comment=comment,
                notification_type=Notification.NotificationType.MENTION,
                message=message,
                url=target_url,
            )
        )
    Notification.objects.bulk_create(notifications)


def submit_poll_vote(user, poll: Poll, option_id: str):
    """Service to record a user's vote on a poll."""
    if not poll.is_open():
        raise ValueError("This poll is closed.")
    option = get_object_or_404(PollOption, poll=poll, pk=option_id)
    PollVote.objects.update_or_create(
        poll=poll,
        user=user,
        defaults={"option": option},
    )


def soft_delete_post(post: Post):
    if post.author_deleted_at is None:
        post.author_deleted_at = django_timezone.now()
        post.save(update_fields=["author_deleted_at", "body_html"])
        dispatch_task(index_post_task, post.pk)
    return post


def restore_post(post: Post):
    if post.author_deleted_at is not None:
        post.author_deleted_at = None
        post.save(update_fields=["author_deleted_at", "body_html"])
        dispatch_task(index_post_task, post.pk)
    return post


def soft_delete_comment(comment: Comment):
    if comment.author_deleted_at is None:
        comment.author_deleted_at = django_timezone.now()
        comment.save(update_fields=["author_deleted_at", "body_html"])
        Post.objects.filter(pk=comment.post_id, comment_count__gt=0).update(comment_count=models.F("comment_count") - 1)
    return comment


def restore_comment(comment: Comment):
    if comment.author_deleted_at is not None:
        comment.author_deleted_at = None
        comment.save(update_fields=["author_deleted_at", "body_html"])
        Post.objects.filter(pk=comment.post_id).update(comment_count=models.F("comment_count") + 1)
    return comment


def build_comment_tree(post: Post, sort: str = "top", max_depth: int = 10, user=None):
    order_map = {
        "top": ["-score", "created_at"],
        "new": ["-created_at"],
        "old": ["created_at"],
    }
    qs = Comment.objects.filter(post=post, is_removed=False).select_related("author")
    if user is not None and getattr(user, "is_authenticated", False):
        qs = qs.filter(Q(author_deleted_at__isnull=True) | Q(author=user))
    else:
        qs = qs.filter(author_deleted_at__isnull=True)
    if user is not None and getattr(user, "is_authenticated", False):
        blocked_ids = list(user.blocked_users.values_list("id", flat=True))
        if blocked_ids:
            qs = qs.exclude(author_id__in=blocked_ids)
    qs = qs.order_by(*order_map.get(sort, ["-score", "created_at"]))
    comments_by_parent: dict[int | None, list[Comment]] = defaultdict(list)
    for comment in qs:
        comments_by_parent[comment.parent_id].append(comment)

    def nest(parent_id, depth=0):
        result = []
        for comment in comments_by_parent.get(parent_id, []):
            comment.depth = depth
            comment.children = nest(comment.id, depth + 1) if depth < max_depth else []
            result.append(comment)
        return result

    tree = nest(None)
    for comment in tree:
        if not hasattr(comment, "children"):
            comment.children = []
    return tree


def annotate_posts_with_user_state(posts, user):
    if not user.is_authenticated or not posts:
        return {post.id: 0 for post in posts}, set()
    post_ids = [post.id for post in posts]
    votes = dict(Vote.objects.filter(user=user, post_id__in=post_ids).values_list("post_id", "value"))
    saved = set(SavedPost.objects.filter(user=user, post_id__in=post_ids).values_list("post_id", flat=True))
    return votes, saved


def build_personalization_profile(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    joined_community_ids = set(user.communitymembership_set.values_list("community_id", flat=True))
    followed_user_ids = set(user.followed_users.values_list("id", flat=True))
    saved_rows = (
        SavedPost.objects.filter(user=user)
        .values("post__community_id", "post__post_type", "post__flair_id")
        .annotate(total=Count("id"))
    )
    saved_communities = {row["post__community_id"] for row in saved_rows if row["post__community_id"]}
    saved_post_types = {row["post__post_type"] for row in saved_rows if row["post__post_type"]}
    saved_flair_ids = {row["post__flair_id"] for row in saved_rows if row["post__flair_id"]}
    commented_rows = (
        Comment.objects.filter(author=user, author_deleted_at__isnull=True)
        .values("post__community_id")
        .annotate(total=Count("id"))
    )
    commented_community_ids = {row["post__community_id"] for row in commented_rows if row["post__community_id"]}
    challenge_community_ids = set(
        CommunityChallenge.objects.filter(participations__user=user).values_list("community_id", flat=True)
    )
    return {
        "joined_community_ids": joined_community_ids,
        "followed_user_ids": followed_user_ids,
        "saved_communities": saved_communities,
        "saved_post_types": saved_post_types,
        "saved_flair_ids": saved_flair_ids,
        "commented_community_ids": commented_community_ids,
        "challenge_community_ids": challenge_community_ids,
    }


def explain_post_reason(post, profile):
    if profile is None:
        if getattr(post, "challenge_context", None):
            return f"Live challenge: {post.challenge_context}"
        return "Trending across Agora"
    if post.author_id in profile["followed_user_ids"]:
        return "Because you follow this person"
    if post.community_id in profile["joined_community_ids"]:
        return "Because you joined this community"
    if post.community_id in profile["commented_community_ids"]:
        return "Because you often comment here"
    if post.community_id in profile["saved_communities"]:
        return "Because you save threads from this community"
    if post.flair_id and post.flair_id in profile["saved_flair_ids"]:
        return "Because this matches what you save"
    if post.post_type in profile["saved_post_types"]:
        return f"Because you save {post.get_post_type_display().lower()} posts"
    if post.community_id in profile["challenge_community_ids"] or getattr(post, "challenge_id", None):
        return "Because you joined a challenge here"
    return "Fresh in your orbit"


def personalize_post_window(posts, user):
    profile = build_personalization_profile(user)
    if not posts:
        return posts
    seen_community_counts = defaultdict(int)
    now = django_timezone.now()
    for post in posts:
        score = float(getattr(post, "personal_boost", 0) or 0)
        if profile is not None:
            if post.author_id in profile["followed_user_ids"]:
                score += 18
            if post.community_id in profile["joined_community_ids"]:
                score += 10
            if post.community_id in profile["saved_communities"]:
                score += 6
            if post.community_id in profile["commented_community_ids"]:
                score += 7
            if post.community_id in profile["challenge_community_ids"]:
                score += 5
            if post.post_type in profile["saved_post_types"]:
                score += 2
            if post.flair_id and post.flair_id in profile["saved_flair_ids"]:
                score += 3
        if getattr(post, "challenge_id", None):
            score += 4
        freshness_hours = max((now - post.created_at).total_seconds() / 3600, 0)
        score += max(0, 8 - min(freshness_hours, 8))
        score -= seen_community_counts[post.community_id] * 3
        post.personalized_score = round(score, 2)
        post.feed_reason = explain_post_reason(post, profile)
        seen_community_counts[post.community_id] += 1
    return sorted(posts, key=lambda post: (-(post.personalized_score), -post.score, -post.comment_count, -post.created_at.timestamp()))


def enrich_posts_for_display(posts, user=None):
    if not posts:
        return posts
    post_ids = [post.id for post in posts]
    comment_meta = {
        row["post_id"]: row
        for row in Comment.objects.filter(post_id__in=post_ids, is_removed=False, author_deleted_at__isnull=True)
        .values("post_id")
        .annotate(
            last_comment_at=Max("created_at"),
            participant_count=Count("author_id", distinct=True),
        )
    }
    active_challenges = {
        challenge.community_id: challenge
        for challenge in CommunityChallenge.objects.filter(
            community_id__in=[post.community_id for post in posts],
            starts_at__lte=models.functions.Now(),
            ends_at__gte=models.functions.Now(),
            is_featured=True,
        ).order_by("-starts_at")
    }
    followed_ids = set()
    profile = build_personalization_profile(user)
    if user is not None and getattr(user, "is_authenticated", False):
        followed_ids = set(user.followed_users.values_list("id", flat=True))

    for post in posts:
        meta = comment_meta.get(post.id, {})
        participant_count = meta.get("participant_count") or 0
        if post.author_id:
            participant_count = max(participant_count, 1)
        post.last_comment_at = meta.get("last_comment_at")
        post.discussion_count = participant_count
        post.discussion_label = (
            f"{participant_count} people are discussing"
            if participant_count > 1
            else "Start the discussion"
        )
        post.is_from_followed_user = post.author_id in followed_ids
        challenge = active_challenges.get(post.community_id)
        post.challenge_context = None
        if challenge and post.created_at >= challenge.starts_at:
            post.challenge_context = challenge.title
        post.feed_reason = getattr(post, "feed_reason", explain_post_reason(post, profile))
    return posts


def apply_post_sort(queryset, sort="hot"):
    return queryset.order_by(*POST_SORT_MAP.get(sort, POST_SORT_MAP["hot"]))


def apply_personalized_post_sort(queryset, sort="hot"):
    sort_fields = POST_SORT_MAP.get(sort, POST_SORT_MAP["hot"])
    return queryset.order_by("-personal_boost", *sort_fields)


def pg_feed_queryset(user, community=None, sort="hot", scope="all"):
    queryset = Post.objects.visible_to(user).for_listing()
    memberships = []
    if user is not None and user.is_authenticated:
        blocked_ids = list(user.blocked_users.values_list("id", flat=True))
        memberships = list(user.communitymembership_set.values_list("community_id", flat=True))
        if blocked_ids:
            queryset = queryset.exclude(author_id__in=blocked_ids)
    if community is not None:
        queryset = queryset.filter(community=community)
    else:
        visible_filters = Q(
            community__community_type__in=[Community.CommunityType.PUBLIC, Community.CommunityType.RESTRICTED]
        )
        if memberships:
            visible_filters |= Q(community_id__in=memberships)
        queryset = queryset.filter(visible_filters)

    if user is not None and user.is_authenticated and community is None:
        followed_users = list(user.followed_users.values_list("id", flat=True))
        if scope == "communities":
            queryset = queryset.filter(community_id__in=memberships) if memberships else queryset.none()
        elif scope == "following":
            queryset = queryset.filter(author_id__in=followed_users) if followed_users else queryset.none()
        else:
            engaged_community_ids = set()
            engaged_community_ids.update(
                Vote.objects.filter(user=user, post__isnull=False).values_list("post__community_id", flat=True)
            )
            engaged_community_ids.update(
                SavedPost.objects.filter(user=user).values_list("post__community_id", flat=True)
            )
            challenge_community_ids = set(
                CommunityChallenge.objects.filter(
                    starts_at__lte=models.functions.Now(),
                    ends_at__gte=models.functions.Now(),
                    is_featured=True,
                ).values_list("community_id", flat=True)
            )
            commented_community_ids = set(
                Comment.objects.filter(author=user, author_deleted_at__isnull=True).values_list("post__community_id", flat=True)
            )
            saved_post_types = set(SavedPost.objects.filter(user=user).values_list("post__post_type", flat=True))
            queryset = queryset.annotate(
                personal_boost=(
                    Case(
                        When(author_id__in=followed_users, then=Value(12)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                    + Case(
                        When(community_id__in=memberships, then=Value(8)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                    + Case(
                        When(community_id__in=engaged_community_ids, then=Value(4)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                    + Case(
                        When(community_id__in=commented_community_ids, then=Value(5)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                    + Case(
                        When(community_id__in=challenge_community_ids, then=Value(2)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                    + Case(
                        When(post_type__in=saved_post_types, then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                )
            )
            return apply_personalized_post_sort(queryset, sort=sort)
    return apply_post_sort(queryset, sort=sort)


def create_reengagement_notifications(comment: Comment):
    from apps.accounts.models import Notification

    recipients = []
    if comment.post.author_id and comment.post.author_id != comment.author_id:
        recipients.append(
            (
                comment.post.author,
                Notification.NotificationType.POST_REPLY,
                f"{comment.author.handle or 'Someone'} replied to your post '{comment.post.title}'.",
            )
        )
    if comment.parent_id and comment.parent and comment.parent.author_id and comment.parent.author_id not in {
        comment.author_id,
        comment.post.author_id,
    }:
        recipients.append(
            (
                comment.parent.author,
                Notification.NotificationType.COMMENT_REPLY,
                f"{comment.author.handle or 'Someone'} replied to your comment in '{comment.post.title}'.",
            )
        )

    url = reverse(
        "post_detail",
        kwargs={
            "community_slug": comment.post.community.slug,
            "post_id": comment.post.id,
            "slug": comment.post.slug,
        },
    )
    for user, notification_type, message in recipients:
        if notification_type in {
            Notification.NotificationType.POST_REPLY,
            Notification.NotificationType.COMMENT_REPLY,
        } and not user.notify_on_replies:
            continue
        Notification.objects.create(
            user=user,
            actor=comment.author,
            community=comment.post.community,
            post=comment.post,
            comment=comment,
            notification_type=notification_type,
            message=message,
            url=url,
        )


def share_links_for_post(post: Post):
    base_url = getattr(settings, "APP_PUBLIC_URL", "").rstrip("/")
    path = f"/c/{post.community.slug}/post/{post.id}/{post.slug}/"
    post_url = f"{base_url}{path}" if base_url else path
    share_message = f"{post.title} — join the conversation in c/{post.community.slug} on {settings.APP_NAME}."
    encoded_url = quote_plus(post_url)
    encoded_text = quote_plus(share_message)
    return {
        "copy_url": post_url,
        "share_text": share_message,
        "whatsapp": f"https://wa.me/?text={encoded_text}%20{encoded_url}",
        "telegram": f"https://t.me/share/url?url={encoded_url}&text={encoded_text}",
        "x": f"https://twitter.com/intent/tweet?text={encoded_text}&url={encoded_url}",
        "email": f"mailto:?subject={quote_plus(post.title)}&body={quote_plus(f'{share_message}\\n\\n{post_url}')}",
    }
