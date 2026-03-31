from .backends import get_discovery_backend, parse_search_query


def search_posts(raw_query, sort="relevance", after=None):
    return get_discovery_backend().search_posts(raw_query, sort=sort, after=after)
