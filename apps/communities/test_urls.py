from django.urls import resolve, reverse

from apps.communities import views
from apps.feeds.views import community_feed


def test_community_urls_reverse_and_resolve_correctly():
    cases = [
        ("create_community", {}, views.create_community),
        ("community_discovery", {}, views.community_discovery),
        ("community_landing", {"slug": "alpha"}, views.community_landing),
        ("community_share_card", {"slug": "alpha"}, views.community_share_card),
        ("community_invite", {"slug": "alpha", "token": "token123"}, views.community_invite),
        ("community_challenge_join", {"slug": "alpha", "challenge_id": 3}, views.join_community_challenge),
        ("community_wiki_edit_home", {"slug": "alpha"}, views.wiki_edit),
        ("community_wiki_edit", {"slug": "alpha", "page_slug": "rules"}, views.wiki_edit),
        ("community_wiki_home", {"slug": "alpha"}, views.wiki_page),
        ("community_wiki_page", {"slug": "alpha", "page_slug": "rules"}, views.wiki_page),
        ("community_settings", {"slug": "alpha"}, views.community_settings),
        ("community_detail", {"slug": "alpha"}, community_feed),
        ("toggle_membership", {"slug": "alpha"}, views.toggle_membership),
    ]

    for name, kwargs, expected_view in cases:
        path = reverse(name, kwargs=kwargs)
        match = resolve(path)
        assert match.func == expected_view
