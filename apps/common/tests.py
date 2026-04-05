from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.communities.models import Community
from apps.posts.models import Post

User = get_user_model()


class CommonFeatureTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="smokeuser",
            email="smokeuser@example.com",
            password="password123",
            handle="smokeuser",
        )
        self.community = Community.objects.create(
            name="Smoke Community",
            slug="smoke-community",
            title="Smoke Community",
            description="Smoke test surface.",
            creator=self.user,
        )
        self.post = Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="Smoke thread",
            body_md="Body",
            score=4,
            hot_score=4,
        )

    def test_manifest_exposes_install_metadata(self):
        response = self.client.get(reverse("web_manifest"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        self.assertContains(response, '"name": "Agora"')

    def test_service_worker_is_served_as_javascript(self):
        response = self.client.get(reverse("service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response["Content-Type"])
        self.assertContains(response, "CACHE_NAME")
        self.assertContains(response, "OFFLINE_URL")

    def test_offline_page_renders(self):
        response = self.client.get(reverse("offline_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You are offline right now")

    def test_markdown_preview_renders_html(self):
        response = self.client.post(reverse("markdown_preview"), {"markdown": "## Preview"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h2>Preview</h2>", html=True)

    def test_public_surface_templates_render(self):
        for url_name, text in (
            ("home", "Smoke thread"),
            ("popular", "Smoke thread"),
            ("community_discovery", "Smoke Community"),
            ("search", "Smoke thread"),
            ("community_detail", "Smoke thread"),
        ):
            kwargs = {"slug": self.community.slug} if url_name == "community_detail" else {}
            params = {"q": "Smoke"} if url_name in {"community_discovery", "search"} else {}
            response = self.client.get(reverse(url_name, kwargs=kwargs), params)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, text)

    def test_authenticated_creation_surfaces_render(self):
        self.client.force_login(self.user)

        profile_response = self.client.get(reverse("profile", kwargs={"handle": self.user.handle}))
        community_create_response = self.client.get(reverse("create_community"))
        post_create_response = self.client.get(reverse("create_post", kwargs={"community_slug": self.community.slug}))
        notifications_response = self.client.get(reverse("notifications"))

        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(profile_response, "Smoke thread")
        self.assertEqual(community_create_response.status_code, 200)
        self.assertContains(community_create_response, "Create a new community")
        self.assertEqual(post_create_response.status_code, 200)
        self.assertContains(post_create_response, "Live preview")
        self.assertEqual(notifications_response.status_code, 200)
