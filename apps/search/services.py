from .backends import get_discovery_backend, parse_search_query


def search_posts(raw_query, sort="relevance", after=None, *, post_type="", media=""):
    return get_discovery_backend().search_posts(
        raw_query,
        sort=sort,
        after=after,
        post_type=post_type,
        media=media,
    )
