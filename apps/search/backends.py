from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass

from django.conf import settings
from django.db.models import Case, IntegerField, Q as DjangoQ, Value, When

from apps.posts.models import Post
from apps.posts.services import apply_post_sort, pg_feed_queryset


OPERATOR_MAP = {
    "author": "author__handle__iexact",
    "flair": "flair__text__iexact",
    "community": "community__slug__iexact",
    "subreddit": "community__slug__iexact",
    "type": "post_type__iexact",
}

ELASTIC_OPERATOR_MAP = {
    "author": "author_handle",
    "flair": "flair_text",
    "community": "community_slug",
    "subreddit": "community_slug",
    "type": "post_type",
}
DJANGO_FILTER_TO_OPERATOR = {value: key for key, value in OPERATOR_MAP.items()}


def parse_search_query(raw_query: str):
    filters = {}
    text_parts = []
    for token in raw_query.split():
        match = re.match(r"(\w+):(\S+)", token)
        if match and match.group(1) in OPERATOR_MAP:
            filters[OPERATOR_MAP[match.group(1)]] = match.group(2)
        else:
            text_parts.append(token)
    return " ".join(text_parts), filters


@dataclass
class FeedResult:
    posts: list[Post]
    next_cursor: str | None = None


class BaseDiscoveryBackend:
    name = "base"

    def home_feed(self, user, sort="hot", page_size=25, after=None, scope="all") -> FeedResult:
        raise NotImplementedError

    def community_feed(self, user, community, sort="hot", page_size=25, after=None) -> FeedResult:
        raise NotImplementedError

    def popular_feed(self, user=None, sort="hot", page_size=25, after=None) -> FeedResult:
        raise NotImplementedError

    def search_posts(self, raw_query, sort="relevance", page_size=50, after=None):
        raise NotImplementedError


class SQLDiscoveryBackend(BaseDiscoveryBackend):
    name = "sql"

    @staticmethod
    def _encode_cursor(offset: int) -> str:
        payload = json.dumps({"offset": offset}, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii")

    @staticmethod
    def _decode_cursor(cursor: str | None) -> int:
        if not cursor:
            return 0
        try:
            payload = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
            return max(0, int(json.loads(payload).get("offset", 0)))
        except Exception:
            return 0

    def _paginate_queryset(self, queryset, page_size=25, after=None) -> FeedResult:
        offset = self._decode_cursor(after)
        posts = list(queryset[offset : offset + page_size])
        next_cursor = self._encode_cursor(offset + page_size) if len(posts) == page_size else None
        return FeedResult(posts, next_cursor=next_cursor)

    def home_feed(self, user, sort="hot", page_size=25, after=None, scope="all") -> FeedResult:
        return self._paginate_queryset(
            pg_feed_queryset(user=user, community=None, sort=sort, scope=scope),
            page_size=page_size,
            after=after,
        )

    def community_feed(self, user, community, sort="hot", page_size=25, after=None) -> FeedResult:
        return self._paginate_queryset(
            pg_feed_queryset(user=user, community=community, sort=sort),
            page_size=page_size,
            after=after,
        )

    def popular_feed(self, user=None, sort="hot", page_size=25, after=None) -> FeedResult:
        return self._paginate_queryset(pg_feed_queryset(user=None, community=None, sort=sort), page_size=page_size, after=after)

    def search_posts(self, raw_query, sort="relevance", page_size=50, after=None, *, post_type="", media=""):
        query_text, filters = parse_search_query(raw_query)
        queryset = Post.objects.visible().for_listing()

        if query_text:
            queryset = queryset.filter(
                DjangoQ(title__icontains=query_text)
                | DjangoQ(body_md__icontains=query_text)
                | DjangoQ(community__title__icontains=query_text)
                | DjangoQ(community__slug__icontains=query_text)
            )

        for field, value in filters.items():
            queryset = queryset.filter(**{field: value})

        if post_type:
            queryset = queryset.filter(post_type__iexact=post_type)
        if media == "images":
            queryset = queryset.filter(image__gt="")
        elif media == "links":
            queryset = queryset.filter(url__gt="")

        if sort in {"hot", "new", "top", "rising"}:
            queryset = apply_post_sort(queryset, sort=sort)
        else:
            queryset = queryset.order_by("-score", "-created_at")
        return self._paginate_queryset(queryset, page_size=page_size, after=after)


class ElasticsearchDiscoveryBackend(BaseDiscoveryBackend):
    name = "elasticsearch"

    def __init__(self):
        from .documents import PostDocument

        self.document = PostDocument
        self.sql_backend = SQLDiscoveryBackend()

    def _sort(self, search, sort: str):
        sort_map = {
            "hot": [{"hot_score": "desc"}, {"created_at": "desc"}],
            "new": [{"created_at": "desc"}],
            "top": [{"score": "desc"}, {"created_at": "desc"}],
            "rising": [{"upvote_count": "desc"}, {"created_at": "desc"}],
            "relevance": [{"_score": "desc"}, {"created_at": "desc"}],
        }
        return search.sort(*sort_map.get(sort, sort_map["hot"]))

    def _ordered_posts(self, ids: list[int]) -> list[Post]:
        if not ids:
            return []
        ordering = Case(
            *[When(pk=post_id, then=Value(index)) for index, post_id in enumerate(ids)],
            output_field=IntegerField(),
        )
        queryset = Post.objects.visible().for_listing().filter(pk__in=ids).annotate(_sort_order=ordering)
        posts_by_id = {post.id: post for post in queryset.order_by("_sort_order")}
        return [posts_by_id[post_id] for post_id in ids if post_id in posts_by_id]

    def _blocked_handles(self, user):
        if user is None or not user.is_authenticated:
            return []
        return list(user.blocked_users.values_list("handle", flat=True))

    def _search_to_posts(self, search, page_size=25, after=None):
        offset = SQLDiscoveryBackend._decode_cursor(after)
        search = search[offset : offset + page_size]
        results = search.execute()
        ids = [int(hit.id) for hit in results]
        next_cursor = SQLDiscoveryBackend._encode_cursor(offset + page_size) if len(ids) == page_size else None
        return FeedResult(self._ordered_posts(ids), next_cursor=next_cursor)

    def home_feed(self, user, sort="hot", page_size=25, after=None, scope="all") -> FeedResult:
        from elasticsearch_dsl import Q as ElasticQ

        if user is None or not user.is_authenticated:
            return self.popular_feed(sort=sort, page_size=page_size, after=after)

        community_slugs = list(user.communitymembership_set.values_list("community__slug", flat=True))
        followed_handles = list(user.followed_users.values_list("handle", flat=True))
        if scope == "communities":
            followed_handles = []
        elif scope == "following":
            community_slugs = []
        if not community_slugs and not followed_handles:
            return self.popular_feed(sort=sort, page_size=page_size)

        search = self.document.search().filter("term", is_removed=False)
        should = []
        if community_slugs:
            should.append(ElasticQ("terms", community_slug=community_slugs))
        if followed_handles:
            should.append(ElasticQ("terms", author_handle=followed_handles))
        search = search.query(ElasticQ("bool", should=should, minimum_should_match=1))
        blocked_handles = self._blocked_handles(user)
        if blocked_handles:
            search = search.exclude("terms", author_handle=blocked_handles)
        search = self._sort(search, sort)
        return self._search_to_posts(search, page_size=page_size, after=after)

    def community_feed(self, user, community, sort="hot", page_size=25, after=None) -> FeedResult:
        search = self.document.search().filter("term", is_removed=False).filter("term", community_slug=community.slug)
        blocked_handles = self._blocked_handles(user)
        if blocked_handles:
            search = search.exclude("terms", author_handle=blocked_handles)
        search = self._sort(search, sort)
        return self._search_to_posts(search, page_size=page_size, after=after)

    def popular_feed(self, user=None, sort="hot", page_size=25, after=None) -> FeedResult:
        search = self.document.search().filter("term", is_removed=False)
        blocked_handles = self._blocked_handles(user)
        if blocked_handles:
            search = search.exclude("terms", author_handle=blocked_handles)
        search = self._sort(search, sort)
        return self._search_to_posts(search, page_size=page_size, after=after)

    def search_posts(self, raw_query, sort="relevance", page_size=50, after=None, *, post_type="", media=""):
        query_text, filters = parse_search_query(raw_query)
        search = self.document.search().filter("term", is_removed=False)

        if query_text:
            search = search.query("multi_match", query=query_text, fields=["title^3", "body_text", "community_name"])

        for field, value in filters.items():
            es_field = ELASTIC_OPERATOR_MAP[DJANGO_FILTER_TO_OPERATOR[field]]
            search = search.filter("term", **{es_field: value})

        if post_type:
            search = search.filter("term", post_type=post_type)
        if media == "images":
            search = search.filter("exists", field="image")
        elif media == "links":
            search = search.filter("exists", field="url")

        search = self._sort(search, sort)
        return self._search_to_posts(search, page_size=page_size, after=after)


def get_discovery_backend() -> BaseDiscoveryBackend:
    backend_name = getattr(settings, "SEARCH_BACKEND", "sql")
    if backend_name == "elasticsearch":
        try:
            if not settings.SEARCH_INDEX_ENABLED:
                return SQLDiscoveryBackend()
            return ElasticsearchDiscoveryBackend()
        except Exception:
            return SQLDiscoveryBackend()
    return SQLDiscoveryBackend()
