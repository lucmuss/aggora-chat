from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO

from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.communities.models import Community, CommunityMembership
from apps.moderation.models import CommunityAgentSettings, ModAction, ModQueueItem
from apps.posts.models import PollVote, Post


User = get_user_model()


class AgentModApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner_api",
            email="owner_api@example.com",
            password="password123",
            handle="owner_api",
        )
        self.agent = User.objects.create_user(
            username="agent_api",
            email="agent_api@example.com",
            password="password123",
            handle="agent_api",
            is_agent=True,
            agent_verified=True,
            agent_provider_issuer="https://issuer.example",
        )
        self.unverified_agent = User.objects.create_user(
            username="agent_unverified",
            email="agent_unverified@example.com",
            password="password123",
            handle="agent_unverified",
            is_agent=True,
            agent_verified=False,
        )
        self.community = Community.objects.create(
            name="Agora Agent API",
            slug="agora-agent-api",
            title="Agora Agent API",
            description="API moderation tests.",
            creator=self.owner,
        )
        CommunityMembership.objects.create(
            user=self.owner,
            community=self.community,
            role=CommunityMembership.Role.OWNER,
        )
        CommunityMembership.objects.create(
            user=self.agent,
            community=self.community,
            role=CommunityMembership.Role.AGENT_MOD,
        )
        self.post = Post.objects.create(
            community=self.community,
            author=self.owner,
            post_type="text",
            title="Target post",
            body_md="Body",
        )
        self.token = Token.objects.create(user=self.agent)
        self.unverified_token = Token.objects.create(user=self.unverified_agent)

    def test_low_confidence_agent_action_queues_item(self):
        CommunityAgentSettings.objects.create(community=self.community, auto_remove_threshold=0.9)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.client.post(
            reverse("api_agent_mod_action", kwargs={"community_slug": self.community.slug}),
            {
                "action": "remove",
                "post_id": self.post.id,
                "confidence": 0.4,
                "reason_code": "toxicity",
                "explanation": "Low confidence but suspicious",
            },
            format="json",
        )

        self.post.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.post.is_removed)
        self.assertEqual(ModQueueItem.objects.count(), 1)
        self.assertEqual(ModAction.objects.filter(action_type=ModAction.ActionType.AGENT_REMOVE).count(), 1)
        self.assertTrue(response.data["queued"])

    def test_high_confidence_remove_auto_removes(self):
        CommunityAgentSettings.objects.create(community=self.community, auto_remove_threshold=0.8)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.client.post(
            reverse("api_agent_mod_action", kwargs={"community_slug": self.community.slug}),
            {
                "action": "remove",
                "post_id": self.post.id,
                "confidence": 0.95,
                "reason_code": "spam",
                "explanation": "High confidence spam",
            },
            format="json",
        )

        self.post.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.post.is_removed)
        self.assertFalse(response.data["queued"])

    def test_unverified_agent_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.unverified_token.key}")

        response = self.client.post(
            reverse("api_agent_mod_action", kwargs={"community_slug": self.community.slug}),
            {
                "action": "flag",
                "post_id": self.post.id,
                "confidence": 0.5,
                "reason_code": "safety",
                "explanation": "Needs review",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_reason_fields_are_required(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.client.post(
            reverse("api_agent_mod_action", kwargs={"community_slug": self.community.slug}),
            {"action": "flag", "post_id": self.post.id, "confidence": 0.5},
            format="json",
        )

        self.assertEqual(response.status_code, 400)


class PublicApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="public_api",
            email="public_api@example.com",
            password="password123",
            handle="public_api",
        )
        self.community = Community.objects.create(
            name="Agora Public API",
            slug="agora-public-api",
            title="Agora Public API",
            description="Public API tests.",
            creator=self.user,
        )
        self.post = Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="API thread",
            body_md="Body",
            score=7,
            hot_score=7,
        )
        self.token = Token.objects.create(user=self.user)

    def test_popular_feed_api_returns_items(self):
        response = self.client.get(reverse("api_popular_feed"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["items"][0]["title"], "API thread")

    def test_search_api_returns_items(self):
        response = self.client.get(reverse("api_search"), {"q": "API"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"][0]["title"], "API thread")

    def test_search_api_returns_matching_communities_and_users(self):
        self.user.display_name = "API Captain"
        self.user.bio = "Builds API search flows."
        self.user.save(update_fields=["display_name", "bio"])

        response = self.client.get(reverse("api_search"), {"q": "api"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["communities"][0]["slug"], self.community.slug)
        self.assertEqual(response.data["users"][0]["handle"], self.user.handle)

    def test_user_profile_api_includes_visibility_mfa_and_badges(self):
        self.user.profile_visibility = User.ProfileVisibility.MEMBERS
        self.user.mfa_totp_enabled = True
        self.user.save(update_fields=["profile_visibility", "mfa_totp_enabled"])
        self.user.badges.create(code="first_steps", title="First Steps", description="Started", icon="➜")

        response = self.client.get(reverse("api_user_profile", kwargs={"handle": self.user.handle}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["profile_visibility"], User.ProfileVisibility.MEMBERS)
        self.assertTrue(response.data["mfa_totp_enabled"])
        self.assertEqual(response.data["badges"][0]["code"], "first_steps")

    def test_authenticated_post_create_api_works(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.client.post(
            reverse("api_post_create"),
            {
                "community_slug": self.community.slug,
                "post_type": "text",
                "title": "Created via API",
                "body_md": "API body",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Post.objects.filter(title="Created via API").count(), 1)

    def test_feed_api_returns_cursor(self):
        for index in range(30):
            Post.objects.create(
                community=self.community,
                author=self.user,
                post_type="text",
                title=f"Cursor API thread {index}",
                body_md="Body",
                score=30 - index,
                hot_score=30 - index,
            )

        response = self.client.get(reverse("api_popular_feed"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["after"])

    def test_post_create_api_validates_polls(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.community.allow_polls = True
        self.community.save(update_fields=["allow_polls"])

        response = self.client.post(
            reverse("api_post_create"),
            {
                "community_slug": self.community.slug,
                "post_type": "poll",
                "title": "API poll",
                "body_md": "Choose one",
                "poll_options": ["Alpha", "Beta"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["poll"]["options"][0]["label"], "Alpha")

    def test_post_create_api_supports_crossposts(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        original = Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="Original thread",
            body_md="Original body",
        )

        response = self.client.post(
            reverse("api_post_create"),
            {
                "community_slug": self.community.slug,
                "post_type": "crosspost",
                "title": "Shared thread",
                "body_md": "Crossposted",
                "crosspost_parent_id": original.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["crosspost_parent_id"], original.id)

    def test_private_community_feed_api_is_hidden_from_anonymous(self):
        self.community.community_type = Community.CommunityType.PRIVATE
        self.community.save(update_fields=["community_type"])

        response = self.client.get(reverse("api_community_feed", kwargs={"slug": self.community.slug}))

        self.assertEqual(response.status_code, 403)

    def test_restricted_community_post_create_api_requires_membership(self):
        outsider = User.objects.create_user(
            username="outsider_api",
            email="outsider_api@example.com",
            password="password123",
            handle="outsider_api",
        )
        outsider_token = Token.objects.create(user=outsider)
        self.community.community_type = Community.CommunityType.RESTRICTED
        self.community.save(update_fields=["community_type"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {outsider_token.key}")

        response = self.client.post(
            reverse("api_post_create"),
            {
                "community_slug": self.community.slug,
                "post_type": "text",
                "title": "Should fail",
                "body_md": "No membership",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_poll_vote_api_records_votes(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.community.allow_polls = True
        self.community.save(update_fields=["allow_polls"])
        create_response = self.client.post(
            reverse("api_post_create"),
            {
                "community_slug": self.community.slug,
                "post_type": "poll",
                "title": "Vote here",
                "body_md": "Pick one",
                "poll_options": ["Alpha", "Beta"],
            },
            format="json",
        )
        option_id = create_response.data["poll"]["options"][0]["id"]

        response = self.client.post(
            reverse("api_poll_vote", kwargs={"pk": create_response.data["id"]}),
            {"option_id": option_id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PollVote.objects.count(), 1)

    def test_post_create_api_supports_images(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        image_file = BytesIO()
        Image.new("RGB", (2, 2), color="#2b5cff").save(image_file, format="PNG")
        image_file.seek(0)
        image = SimpleUploadedFile("api-image.png", image_file.read(), content_type="image/png")

        response = self.client.post(
            reverse("api_post_create"),
            {
                "community_slug": self.community.slug,
                "post_type": "image",
                "title": "Image via API",
                "body_md": "Image body",
                "image": image,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["image_url"])
