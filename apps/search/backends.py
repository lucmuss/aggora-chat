from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass

from django.db.models import Q as DjangoQ

from apps.accounts.regions import COUNTRY_CODE_BY_NAME
from apps.posts.models import Post
from apps.posts.services import apply_post_sort, personalize_post_window, pg_feed_queryset

VIDEO_URL_PATTERN = re.compile(
    r"(youtube\.com|youtu\.be|vimeo\.com|tiktok\.com|dailymotion\.com|loom\.com|wistia\.(com|net))",
    re.IGNORECASE,
)
COUNTRY_NAME_BY_CODE = {code.upper(): name for name, code in COUNTRY_CODE_BY_NAME.items() if code}

OPERATOR_MAP = {
    "author": "author__handle__iexact",
    "flair": "flair__text__iexact",
    "community": "community__slug__iexact",
    "subreddit": "community__slug__iexact",
    "type": "post_type__iexact",
    "country": "author__country__iexact",
}

def parse_search_query(raw_query: str):
    filters = {}
    text_parts = []
    for token in raw_query.split():
        match = re.match(r"(\w+):(\S+)", token)
        if match and match.group(1) in OPERATOR_MAP:
            operator = match.group(1)
            value = match.group(2)
            if operator == "country":
                normalized = COUNTRY_NAME_BY_CODE.get(value.upper(), value.replace("-", " ").replace("_", " ").title())
                filters[OPERATOR_MAP[operator]] = normalized
            else:
                filters[OPERATOR_MAP[operator]] = value
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

    def search_posts(self, raw_query, sort="relevance", page_size=50, after=None, user=None):
        raise NotImplementedError


class SQLDiscoveryBackend(BaseDiscoveryBackend):
    name = "sql"

    @staticmethod
    def _apply_media_filter(queryset, media: str):
        if media == "images":
            return queryset.filter(image__gt="")
        if media == "links":
            return queryset.filter(url__gt="")
        if media == "videos":
            return queryset.filter(url__iregex=VIDEO_URL_PATTERN.pattern)
        return queryset

    @staticmethod
    def _apply_post_type_filter(queryset, post_type: str):
        if post_type == "video":
            return queryset.filter(post_type__iexact="link").filter(url__iregex=VIDEO_URL_PATTERN.pattern)
        if post_type:
            return queryset.filter(post_type__iexact=post_type)
        return queryset

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

    def _paginate_personalized_queryset(self, queryset, user, page_size=25, after=None) -> FeedResult:
        offset = self._decode_cursor(after)
        window_size = max(page_size * 3, 60)
        posts = list(queryset[offset : offset + window_size])
        ranked_posts = personalize_post_window(posts, user)
        paginated = ranked_posts[:page_size]
        next_cursor = self._encode_cursor(offset + page_size) if len(posts) >= page_size else None
        return FeedResult(paginated, next_cursor=next_cursor)

    def home_feed(self, user, sort="hot", page_size=25, after=None, scope="all") -> FeedResult:
        queryset = pg_feed_queryset(user=user, community=None, sort=sort, scope=scope)
        if user is not None and getattr(user, "is_authenticated", False) and scope == "all":
            return self._paginate_personalized_queryset(queryset, user=user, page_size=page_size, after=after)
        return self._paginate_queryset(queryset, page_size=page_size, after=after)

    def community_feed(self, user, community, sort="hot", page_size=25, after=None) -> FeedResult:
        return self._paginate_queryset(
            pg_feed_queryset(user=user, community=community, sort=sort),
            page_size=page_size,
            after=after,
        )

    def popular_feed(self, user=None, sort="hot", page_size=25, after=None) -> FeedResult:
        return self._paginate_queryset(pg_feed_queryset(user=None, community=None, sort=sort), page_size=page_size, after=after)

    def search_posts(self, raw_query, sort="relevance", page_size=50, after=None, *, post_type="", media="", user=None):
        query_text, filters = parse_search_query(raw_query)
        queryset = Post.objects.visible_to(user).for_listing()

        if query_text:
            queryset = queryset.filter(
                DjangoQ(title__icontains=query_text)
                | DjangoQ(body_md__icontains=query_text)
                | DjangoQ(community__title__icontains=query_text)
                | DjangoQ(community__slug__icontains=query_text)
            )

        for field, value in filters.items():
            if field == "post_type__iexact" and value.lower() == "video":
                queryset = self._apply_post_type_filter(queryset, "video")
            else:
                queryset = queryset.filter(**{field: value})

        queryset = self._apply_post_type_filter(queryset, post_type)
        queryset = self._apply_media_filter(queryset, media)

        if sort in {"hot", "new", "top", "rising"}:
            queryset = apply_post_sort(queryset, sort=sort)
        else:
            queryset = queryset.order_by("-score", "-created_at")
        return self._paginate_queryset(queryset, page_size=page_size, after=after)


def get_discovery_backend() -> BaseDiscoveryBackend:
    return SQLDiscoveryBackend()
