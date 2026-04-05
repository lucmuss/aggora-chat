from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.communities.models import Community
from apps.posts.models import Post

from .backends import get_discovery_backend, parse_search_query

User = get_user_model()


class SearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="searcher",
            email="searcher@example.com",
            password="password123",
            handle="searcher",
        )
        self.community = Community.objects.create(
            name="Agora Search",
            slug="agora-search",
            title="Agora Search",
            description="Search tests.",
            creator=self.user,
        )
        self.post = Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="Safety policy draft",
            body_md="This covers moderation policy",
            score=10,
            hot_score=10,
        )

    def test_parse_search_query_extracts_operators(self):
        text, filters = parse_search_query("author:searcher community:agora-search policy")

        self.assertEqual(text, "policy")
        self.assertEqual(filters["author__handle__iexact"], "searcher")
        self.assertEqual(filters["community__slug__iexact"], "agora-search")

    def test_search_view_returns_matching_post(self):
        response = self.client.get(reverse("search"), {"q": "policy"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Safety policy draft")

    def test_search_operator_filters_work(self):
        response = self.client.get(reverse("search"), {"q": "author:searcher community:agora-search"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Safety policy draft")

    def test_search_view_returns_matching_community_and_user(self):
        self.user.display_name = "Search Captain"
        self.user.bio = "Writes policy drafts."
        self.user.save(update_fields=["display_name", "bio"])

        response = self.client.get(reverse("search"), {"q": "search"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agora Search")
        self.assertContains(response, "Search Captain")

    def test_search_view_supports_post_type_filter(self):
        Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="link",
            title="Link only result",
            body_md="A link post",
            url="https://example.com",
            score=5,
            hot_score=5,
        )

        response = self.client.get(reverse("search"), {"q": "result", "post_type": "link"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Link only result")
        self.assertNotContains(response, "Safety policy draft")

    def test_search_view_can_focus_on_communities_tab(self):
        response = self.client.get(reverse("search"), {"q": "search", "type": "communities"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matching communities")
        self.assertContains(response, "Agora Search")
        self.assertNotContains(response, "Matching people")

    def test_search_view_can_focus_on_people_tab_with_helpful_empty_state(self):
        response = self.client.get(reverse("search"), {"q": "nobody-here", "type": "people"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No people matched that search yet.")

    def test_quick_search_returns_recent_searches_for_short_query(self):
        session = self.client.session
        session["recent_searches"] = ["design systems", "community prompts"]
        session.save()

        response = self.client.get(reverse("search_quick"), {"mode": "dropdown", "q": "d"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent searches")
        self.assertContains(response, "design systems")

    def test_quick_search_returns_grouped_matches_for_long_query(self):
        self.user.display_name = "Search Captain"
        self.user.save(update_fields=["display_name"])

        response = self.client.get(reverse("search_quick"), {"mode": "palette", "q": "search"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Communities")
        self.assertContains(response, "People")
        self.assertContains(response, "Threads")
        self.assertContains(response, "View all results for")

    @override_settings(SEARCH_BACKEND="sql", SEARCH_INDEX_ENABLED=False)
    def test_sql_backend_is_default_runtime_backend(self):
        backend = get_discovery_backend()

        self.assertEqual(backend.name, "sql")

    @override_settings(SEARCH_BACKEND="elasticsearch", SEARCH_INDEX_ENABLED=False)
    def test_elasticsearch_backend_falls_back_to_sql_when_disabled(self):
        backend = get_discovery_backend()

        self.assertEqual(backend.name, "sql")
