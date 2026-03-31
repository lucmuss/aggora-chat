from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone

from django.db.models import Q

from apps.votes.models import SavedPost, Vote

from .models import Comment, Post


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
