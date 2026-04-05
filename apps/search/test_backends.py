import types

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.communities.models import Community
from apps.posts.models import Post
from apps.search.backends import FeedResult, SQLDiscoveryBackend, get_discovery_backend
from apps.search.queries import community_feed_results, home_feed_results, popular_feed_results
from apps.search.services import search_posts
from apps.search.tasks import index_post_task


User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "search_backend_user"),
        "email": overrides.pop("email", "search_backend_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "search_backend_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="search-backend", creator=None, **overrides):
    creator = creator or make_user(
        username=f"{slug}_creator",
        email=f"{slug}_creator@example.com",
        handle=f"{slug}_creator",
    )
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "Search backend tests",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestSearchBackends:
    def test_sql_backend_decode_cursor_returns_zero_for_invalid_payload(self):
        assert SQLDiscoveryBackend._decode_cursor(None) == 0
        assert SQLDiscoveryBackend._decode_cursor("not-base64") == 0

    def test_sql_search_posts_supports_media_filters_and_fallback_sort(self):
        user = make_user(username="search_media", email="search_media@example.com", handle="search_media")
        community = make_community("search-media", creator=user)
        image_post = Post.objects.create(
            community=community,
            author=user,
            post_type=Post.PostType.IMAGE,
            title="Image result",
            body_md="Body",
            image="post_images/example.png",
            score=3,
            hot_score=3,
        )
        link_post = Post.objects.create(
            community=community,
            author=user,
            post_type=Post.PostType.LINK,
            title="Link result",
            body_md="Body",
            url="https://example.com",
            score=9,
            hot_score=9,
        )
        backend = SQLDiscoveryBackend()

        image_results = backend.search_posts("result", media="images")
        link_results = backend.search_posts("result", media="links")
        fallback_results = backend.search_posts("result", sort="unexpected")

        assert [post.title for post in image_results.posts] == [image_post.title]
        assert [post.title for post in link_results.posts] == [link_post.title]
        assert fallback_results.posts[0].title == link_post.title

    def test_search_service_forwards_filters_to_backend(self, monkeypatch):
        calls = {}

        class FakeBackend:
            def search_posts(self, raw_query, sort="relevance", after=None, post_type="", media=""):
                calls.update(
                    {
                        "raw_query": raw_query,
                        "sort": sort,
                        "after": after,
                        "post_type": post_type,
                        "media": media,
                    }
                )
                return FeedResult([])

        monkeypatch.setattr("apps.search.services.get_discovery_backend", lambda: FakeBackend())

        search_posts("author:test prompt", sort="top", after="abc", post_type="link", media="links")

        assert calls == {
            "raw_query": "author:test prompt",
            "sort": "top",
            "after": "abc",
            "post_type": "link",
            "media": "links",
        }

    def test_query_wrappers_return_posts_and_cursor(self, monkeypatch):
        user = make_user(username="wrapper_user", email="wrapper_user@example.com", handle="wrapper_user")
        community = make_community("wrapper-community", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Wrapped", body_md="Body")

        class FakeBackend:
            def home_feed(self, **kwargs):
                return FeedResult([post], next_cursor="home-cursor")

            def community_feed(self, **kwargs):
                return FeedResult([post], next_cursor="community-cursor")

            def popular_feed(self, **kwargs):
                return FeedResult([post], next_cursor="popular-cursor")

        monkeypatch.setattr("apps.search.queries.get_discovery_backend", lambda: FakeBackend())

        home_posts, home_cursor = home_feed_results(user, scope="following")
        community_posts, community_cursor = community_feed_results(user, community)
        popular_posts, popular_cursor = popular_feed_results(user=user)

        assert home_posts == [post]
        assert community_posts == [post]
        assert popular_posts == [post]
        assert (home_cursor, community_cursor, popular_cursor) == (
            "home-cursor",
            "community-cursor",
            "popular-cursor",
        )

    @override_settings(SEARCH_BACKEND="elasticsearch", SEARCH_INDEX_ENABLED=False)
    def test_get_discovery_backend_falls_back_to_sql_when_indexing_disabled(self):
        backend = get_discovery_backend()

        assert backend.name == "sql"

    @override_settings(SEARCH_BACKEND="elasticsearch", SEARCH_INDEX_ENABLED=True)
    def test_get_discovery_backend_falls_back_to_sql_when_elastic_setup_errors(self, monkeypatch):
        monkeypatch.setattr("apps.search.backends.ElasticsearchDiscoveryBackend", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

        backend = get_discovery_backend()

        assert backend.name == "sql"

    def test_index_post_task_noops_for_sql_backend(self, settings, monkeypatch):
        settings.SEARCH_BACKEND = "sql"
        settings.SEARCH_INDEX_ENABLED = False
        called = {"updated": False}

        class FakeDocument:
            def update(self, post):
                called["updated"] = True

        monkeypatch.setattr("apps.search.documents.PostDocument", FakeDocument)

        assert index_post_task(123) is None
        assert called["updated"] is False

    def test_index_post_task_updates_document_for_elasticsearch_backend(self, settings, monkeypatch):
        user = make_user(username="task_user", email="task_user@example.com", handle="task_user")
        community = make_community("task-community", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Index me", body_md="Body")
        settings.SEARCH_BACKEND = "elasticsearch"
        settings.SEARCH_INDEX_ENABLED = True
        updates = []

        class FakeDocument:
            def update(self, indexed_post):
                updates.append(indexed_post.pk)

        monkeypatch.setattr("apps.search.documents.PostDocument", FakeDocument)

        index_post_task(post.id)

        assert updates == [post.id]

