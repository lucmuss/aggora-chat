from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone

from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.common.celery import dispatch_task
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

    return nest(None)


def annotate_posts_with_user_state(posts, user):
    if not user.is_authenticated or not posts:
        return {post.id: 0 for post in posts}, set()
    post_ids = [post.id for post in posts]
    votes = dict(Vote.objects.filter(user=user, post_id__in=post_ids).values_list("post_id", "value"))
    saved = set(SavedPost.objects.filter(user=user, post_id__in=post_ids).values_list("post_id", flat=True))
    return votes, saved


def apply_post_sort(queryset, sort="hot"):
    return queryset.order_by(*POST_SORT_MAP.get(sort, POST_SORT_MAP["hot"]))


def pg_feed_queryset(user, community=None, sort="hot"):
    queryset = Post.objects.visible().for_listing()
    if user is not None and user.is_authenticated:
        blocked_ids = list(user.blocked_users.values_list("id", flat=True))
        if blocked_ids:
            queryset = queryset.exclude(author_id__in=blocked_ids)
    if community is not None:
        queryset = queryset.filter(community=community)
    elif user is not None and user.is_authenticated:
        memberships = user.communitymembership_set.values_list("community_id", flat=True)
        followed_users = user.followed_users.values_list("id", flat=True)
        filters = Q()
        if memberships:
            filters |= Q(community_id__in=memberships)
        if followed_users:
            filters |= Q(author_id__in=followed_users)
        if filters:
            queryset = queryset.filter(filters)
    return apply_post_sort(queryset, sort=sort)
