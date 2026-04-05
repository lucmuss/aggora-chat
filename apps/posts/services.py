from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import quote_plus

from django.conf import settings
from django.db import models
from django.db.models import Case, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404
from django.urls import reverse

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
    from apps.accounts.growth import award_comment_badges

    award_comment_badges(user)
    return comment


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


def build_comment_tree(post: Post, sort: str = "top", max_depth: int = 10, user=None):
    order_map = {
        "top": ["-score", "created_at"],
        "new": ["-created_at"],
        "old": ["created_at"],
    }
    qs = Comment.objects.filter(post=post, is_removed=False).select_related("author")
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


def apply_post_sort(queryset, sort="hot"):
    return queryset.order_by(*POST_SORT_MAP.get(sort, POST_SORT_MAP["hot"]))


def apply_personalized_post_sort(queryset, sort="hot"):
    sort_fields = POST_SORT_MAP.get(sort, POST_SORT_MAP["hot"])
    return queryset.order_by("-personal_boost", *sort_fields)


def pg_feed_queryset(user, community=None, sort="hot", scope="all"):
    queryset = Post.objects.visible().for_listing()
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
            if memberships:
                queryset = queryset.filter(community_id__in=memberships)
            else:
                queryset = queryset.none()
        elif scope == "following":
            if followed_users:
                queryset = queryset.filter(author_id__in=followed_users)
            else:
                queryset = queryset.none()
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
                        When(community_id__in=challenge_community_ids, then=Value(2)),
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
