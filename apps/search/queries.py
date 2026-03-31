from .backends import get_discovery_backend


def home_feed_results(user, sort="hot", page_size=25, after=None):
    result = get_discovery_backend().home_feed(user=user, sort=sort, page_size=page_size, after=after)
    return result.posts, result.next_cursor


def community_feed_results(user, community, sort="hot", page_size=25, after=None):
    result = get_discovery_backend().community_feed(
        user=user,
        community=community,
        sort=sort,
        page_size=page_size,
        after=after,
    )
    return result.posts, result.next_cursor


def popular_feed_results(sort="hot", page_size=25, user=None, after=None):
    result = get_discovery_backend().popular_feed(user=user, sort=sort, page_size=page_size, after=after)
    return result.posts, result.next_cursor
