from django.core.cache import cache


def get_cached_feed(cache_key):
    return cache.get(cache_key)


def set_cached_feed(cache_key, posts, timeout=60):
    cache.set(cache_key, posts, timeout=timeout)


def community_feed_cache_key(slug, sort):
    return f"feed:community:{slug}:{sort}"


def popular_feed_cache_key(sort):
    return f"feed:popular:{sort}"
