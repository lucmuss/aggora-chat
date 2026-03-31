from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Community, CommunityMembership, CommunityWikiPage


User = get_user_model()


class CommunityFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="creator",
            email="creator@example.com",
            password="password123",
            handle="creator",
        )
        self.community = Community.objects.create(
            name="Agora Builders",
            slug="agora-builders",
            title="Agora Builders",
            description="A home for building Agora.",
            creator=self.user,
        )

    def test_create_community_assigns_owner_membership(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("create_community"),
            {
                "name": "Agora Research",
                "slug": "agora-research",
                "title": "Agora Research",
                "description": "A home for building Agora.",
                "sidebar_md": "## Welcome",
                "community_type": "public",
            },
        )

        community = Community.objects.get(slug="agora-research")
        membership = CommunityMembership.objects.get(user=self.user, community=community)

        self.assertRedirects(response, reverse("community_detail", kwargs={"slug": community.slug}))
        self.assertEqual(membership.role, CommunityMembership.Role.OWNER)
        self.assertEqual(community.subscriber_count, 1)

    def test_community_detail_renders(self):
        response = self.client.get(reverse("community_detail", kwargs={"slug": self.community.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agora Builders")
        self.assertContains(response, "About this community")

    def test_owner_can_update_community_settings(self):
        CommunityMembership.objects.create(
            user=self.user,
            community=self.community,
            role=CommunityMembership.Role.OWNER,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("community_settings", kwargs={"slug": self.community.slug}),
            {
                "title": "Agora Builders Updated",
                "description": "Updated description",
                "sidebar_md": "## Rules",
                "community_type": "public",
                "allow_text_posts": "on",
                "allow_link_posts": "on",
                "allow_image_posts": "on",
                "vote_hide_minutes": 120,
            },
        )

        self.community.refresh_from_db()
        self.assertRedirects(response, reverse("community_detail", kwargs={"slug": self.community.slug}))
        self.assertEqual(self.community.title, "Agora Builders Updated")
        self.assertEqual(self.community.vote_hide_minutes, 120)

    def test_owner_can_create_wiki_page(self):
        CommunityMembership.objects.create(
            user=self.user,
            community=self.community,
            role=CommunityMembership.Role.OWNER,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("community_wiki_edit_home", kwargs={"slug": self.community.slug}),
            {
                "slug": "home",
                "title": "Welcome",
                "body_md": "## Start here",
            },
        )

        wiki_page = CommunityWikiPage.objects.get(community=self.community, slug="home")
        self.assertRedirects(
            response,
            reverse("community_wiki_page", kwargs={"slug": self.community.slug, "page_slug": wiki_page.slug}),
        )
        self.assertIn("Start here", wiki_page.body_html)
