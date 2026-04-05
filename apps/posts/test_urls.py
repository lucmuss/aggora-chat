from django.urls import resolve, reverse

from apps.posts import views


def test_posts_urls_reverse_and_resolve_correctly():
    cases = [
        ("create_post", {"community_slug": "alpha"}, views.create_post),
        ("post_detail", {"community_slug": "alpha", "post_id": 4, "slug": "thread"}, views.post_detail),
        ("create_comment", {"post_id": 4}, views.create_comment),
        ("vote_poll", {"post_id": 4}, views.vote_poll),
    ]

    for name, kwargs, expected_view in cases:
        path = reverse(name, kwargs=kwargs)
        match = resolve(path)
        assert match.func == expected_view
