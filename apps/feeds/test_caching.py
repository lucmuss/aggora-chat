import pytest
from django.core.cache import cache

from apps.feeds.caching import (
    community_feed_cache_key,
    get_cached_feed,
    popular_feed_cache_key,
    set_cached_feed,
)


@pytest.mark.django_db
class TestFeedCaching:
    def test_set_and_get_cached_feed_roundtrip(self):
        cache.clear()
        key = community_feed_cache_key("design", "hot")
        payload = [{"id": 1, "title": "Cached"}]

        set_cached_feed(key, payload, timeout=30)

        assert get_cached_feed(key) == payload

    def test_cache_key_helpers_build_expected_namespaces(self):
        assert community_feed_cache_key("design", "new") == "feed:community:design:new"
        assert popular_feed_cache_key("top") == "feed:popular:top"
