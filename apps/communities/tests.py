from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserBadge
from apps.posts.models import Post

from .models import (
    Community,
    CommunityChallenge,
    CommunityChallengeParticipation,
    CommunityInvite,
    CommunityMembership,
    CommunityWikiPage,
)

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

    def test_create_community_with_starter_kit_prefills_rules_flairs_wiki_and_challenge(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("create_community"),
            {
                "starter_template": "discussion_club",
                "name": "Agora Prompts",
                "slug": "agora-prompts",
                "title": "Agora Prompts",
                "description": "Prompt-driven room",
                "sidebar_md": "",
                "community_type": "public",
            },
        )

        community = Community.objects.get(slug="agora-prompts")

        self.assertRedirects(response, reverse("community_detail", kwargs={"slug": community.slug}))
        self.assertGreaterEqual(community.rules.count(), 1)
        self.assertGreaterEqual(community.post_flairs.count(), 1)
        self.assertTrue(CommunityWikiPage.objects.filter(community=community, slug="home").exists())
        self.assertTrue(CommunityChallenge.objects.filter(community=community).exists())

    def test_community_detail_renders(self):
        response = self.client.get(reverse("community_detail", kwargs={"slug": self.community.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agora Builders")
        self.assertContains(response, "Community Settings")

    def test_non_moderators_do_not_see_moderation_links_on_community_page(self):
        member = User.objects.create_user(
            username="regularmember",
            email="regularmember@example.com",
            password="password123",
            handle="regularmember",
        )
        self.client.force_login(member)

        response = self.client.get(reverse("community_detail", kwargs={"slug": self.community.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Moderation & Growth")

    def test_owner_can_update_community_settings(self):
        self.user.mfa_totp_enabled = True
        self.user.save(update_fields=["mfa_totp_enabled"])
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
        self.user.mfa_totp_enabled = True
        self.user.save(update_fields=["mfa_totp_enabled"])
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

    def test_public_landing_page_renders_invite_and_best_of_sections(self):
        Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="Best thread",
            body_md="Highlight",
            score=9,
            hot_score=9,
        )
        self.community.landing_intro_md = "Welcome builders."
        self.community.faq_md = "## FAQ\n\nHow do I join?"
        self.community.save()

        response = self.client.get(reverse("community_landing", kwargs={"slug": self.community.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "One-click invite")
        self.assertContains(response, "Best thread")
        self.assertContains(response, "Typical topics")
        self.assertContains(response, "Posts this week")

    def test_invite_link_joins_user_and_redirects_to_post_create(self):
        joining_user = User.objects.create_user(
            username="joiner",
            email="joiner@example.com",
            password="password123",
            handle="joiner",
        )
        invite = CommunityInvite.objects.create(community=self.community, created_by=self.user, token="invite-token-1")
        self.client.force_login(joining_user)

        response = self.client.post(reverse("community_invite", kwargs={"slug": self.community.slug, "token": invite.token}))

        self.assertRedirects(response, reverse("create_post", kwargs={"community_slug": self.community.slug}))
        self.assertTrue(CommunityMembership.objects.filter(user=joining_user, community=self.community).exists())
        self.assertTrue(UserBadge.objects.filter(user=self.user, code=UserBadge.BadgeCode.FIRST_REFERRAL).exists())

    def test_community_detail_renders_active_challenge_and_leaderboard(self):
        CommunityMembership.objects.create(
            user=self.user,
            community=self.community,
            role=CommunityMembership.Role.OWNER,
        )
        Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="Leaderboard thread",
            body_md="Body",
            score=12,
            hot_score=12,
        )
        CommunityChallenge.objects.create(
            community=self.community,
            created_by=self.user,
            title="Weekly prompt",
            prompt_md="Share what you're building.",
            starts_at=timezone.now() - timezone.timedelta(days=1),
            ends_at=timezone.now() + timezone.timedelta(days=6),
        )

        response = self.client.get(reverse("community_detail", kwargs={"slug": self.community.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Weekly prompt")
        self.assertContains(response, "Top Contributors This Week")

    def test_logged_in_user_can_join_active_challenge(self):
        member = User.objects.create_user(
            username="challengejoiner",
            email="challengejoiner@example.com",
            password="password123",
            handle="challengejoiner",
        )
        CommunityMembership.objects.create(
            user=member,
            community=self.community,
            role=CommunityMembership.Role.MEMBER,
        )
        challenge = CommunityChallenge.objects.create(
            community=self.community,
            created_by=self.user,
            title="Share your setup",
            prompt_md="Post one screenshot or workflow note.",
            starts_at=timezone.now() - timezone.timedelta(days=1),
            ends_at=timezone.now() + timezone.timedelta(days=5),
        )
        self.client.force_login(member)

        response = self.client.post(
            reverse("community_challenge_join", kwargs={"slug": self.community.slug, "challenge_id": challenge.id})
        )

        self.assertRedirects(response, reverse("community_detail", kwargs={"slug": self.community.slug}))
        self.assertTrue(CommunityChallengeParticipation.objects.filter(user=member, challenge=challenge).exists())

    def test_private_community_is_hidden_from_anonymous_discovery_and_detail(self):
        self.community.community_type = Community.CommunityType.PRIVATE
        self.community.save(update_fields=["community_type"])

        discovery_response = self.client.get(reverse("community_discovery"))
        detail_response = self.client.get(reverse("community_detail", kwargs={"slug": self.community.slug}))

        self.assertEqual(discovery_response.status_code, 200)
        self.assertNotContains(discovery_response, "Agora Builders")
        self.assertEqual(detail_response.status_code, 403)

    def test_restricted_community_requires_invite_to_join(self):
        joining_user = User.objects.create_user(
            username="restricted_joiner",
            email="restricted_joiner@example.com",
            password="password123",
            handle="restricted_joiner",
        )
        self.community.community_type = Community.CommunityType.RESTRICTED
        self.community.save(update_fields=["community_type"])
        self.client.force_login(joining_user)

        response = self.client.post(reverse("toggle_membership", kwargs={"slug": self.community.slug}))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "This community needs an invite", status_code=403)

    def test_share_card_page_renders(self):
        response = self.client.get(reverse("community_share_card", kwargs={"slug": self.community.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "One click to join, one more to post.")
