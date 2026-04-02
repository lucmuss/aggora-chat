from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.communities.models import Community
from apps.posts.models import Post


User = get_user_model()


class DiscoveryFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="discoverer",
            email="discoverer@example.com",
            password="password123",
            handle="discoverer",
        )
        self.community = Community.objects.create(
            name="Agora Popular",
            slug="agora-popular",
            title="Agora Popular",
            description="Discovery tests.",
            creator=self.user,
            subscriber_count=12,
        )
        self.post = Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="Popular thread",
            body_md="Popular body",
            score=12,
            hot_score=12,
        )

    def test_popular_feed_renders(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("popular"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Popular thread")

    def test_community_discovery_renders(self):
        response = self.client.get(reverse("community_discovery"), {"q": "popular"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agora Popular")

    def test_home_feed_includes_followed_users_and_hides_blocked_users(self):
        followed_author = User.objects.create_user(
            username="followed",
            email="followed@example.com",
            password="password123",
            handle="followed",
        )
        blocked_author = User.objects.create_user(
            username="blocked",
            email="blocked@example.com",
            password="password123",
            handle="blocked",
        )
        followed_post = Post.objects.create(
            community=self.community,
            author=followed_author,
            post_type="text",
            title="Followed thread",
            body_md="Visible",
            score=8,
            hot_score=8,
        )
        Post.objects.create(
            community=self.community,
            author=blocked_author,
            post_type="text",
            title="Blocked thread",
            body_md="Hidden",
            score=9,
            hot_score=9,
        )
        self.user.followed_users.add(followed_author)
        self.user.blocked_users.add(blocked_author)
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, followed_post.title)
        self.assertNotContains(response, "Blocked thread")

    def test_home_feed_scope_can_focus_following(self):
        followed_author = User.objects.create_user(
            username="followingonly",
            email="followingonly@example.com",
            password="password123",
            handle="followingonly",
        )
        joined_author = User.objects.create_user(
            username="communityonly",
            email="communityonly@example.com",
            password="password123",
            handle="communityonly",
        )
        community_post = Post.objects.create(
            community=self.community,
            author=joined_author,
            post_type="text",
            title="Community only thread",
            body_md="Community only",
            score=4,
            hot_score=4,
        )
        following_post = Post.objects.create(
            community=self.community,
            author=followed_author,
            post_type="text",
            title="Following only thread",
            body_md="Following only",
            score=6,
            hot_score=6,
        )
        self.user.followed_users.add(followed_author)
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"), {"scope": "following"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, following_post.title)
        self.assertNotContains(response, community_post.title)
