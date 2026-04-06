from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.communities.models import Community, CommunityMembership
from apps.posts.models import Comment, Post

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

    def test_home_feed_hides_nsfw_posts_until_user_opts_in(self):
        Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="Adults only thread",
            body_md="Hidden unless opted in",
            score=15,
            hot_score=15,
            is_nsfw=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Adults only thread")

        self.user.allow_nsfw_content = True
        self.user.save(update_fields=["allow_nsfw_content"])
        response = self.client.get(reverse("home"))

        self.assertContains(response, "Adults only thread")

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

    def test_for_you_feed_prioritizes_followed_and_joined_signals(self):
        followed_author = User.objects.create_user(
            username="priorityfollowed",
            email="priorityfollowed@example.com",
            password="password123",
            handle="priorityfollowed",
        )
        other_author = User.objects.create_user(
            username="priorityother",
            email="priorityother@example.com",
            password="password123",
            handle="priorityother",
        )
        joined_community = Community.objects.create(
            name="Joined Signals",
            slug="joined-signals",
            title="Joined Signals",
            description="Joined feed tests.",
            creator=self.user,
        )
        CommunityMembership.objects.create(user=self.user, community=joined_community)
        low_score_followed = Post.objects.create(
            community=self.community,
            author=followed_author,
            post_type="text",
            title="Followed priority thread",
            body_md="Priority",
            score=1,
            hot_score=1,
        )
        high_score_other = Post.objects.create(
            community=self.community,
            author=other_author,
            post_type="text",
            title="Other high score thread",
            body_md="Other",
            score=20,
            hot_score=20,
        )
        joined_post = Post.objects.create(
            community=joined_community,
            author=other_author,
            post_type="text",
            title="Joined community thread",
            body_md="Joined",
            score=2,
            hot_score=2,
        )
        self.user.followed_users.add(followed_author)
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"), {"scope": "all"})

        self.assertEqual(response.status_code, 200)
        posts = list(response.context["posts"])
        self.assertEqual(posts[0].title, low_score_followed.title)
        self.assertEqual(posts[0].feed_reason, "Because you follow this person")
        self.assertIn(joined_post.title, [post.title for post in posts[:3]])
        self.assertIn(high_score_other.title, [post.title for post in posts])
        self.assertContains(response, "Why you see this")

    def test_home_feed_surfaces_friend_activity(self):
        followed_author = User.objects.create_user(
            username="activityfriend",
            email="activityfriend@example.com",
            password="password123",
            handle="activityfriend",
        )
        self.user.followed_users.add(followed_author)
        activity_post = Post.objects.create(
            community=self.community,
            author=followed_author,
            post_type="text",
            title="Activity thread",
            body_md="Activity",
            score=5,
            hot_score=5,
        )
        Comment.objects.create(
            post=activity_post,
            author=followed_author,
            body_md="Recent reply",
            created_at=timezone.now(),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Friend Activity")
        self.assertContains(response, "activityfriend")

    def test_home_feed_shows_first_week_mission_and_conversation_context(self):
        self.client.force_login(self.user)
        Comment.objects.create(
            post=self.post,
            author=self.user,
            body_md="Fresh reply",
            body_html="<p>Fresh reply</p>",
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "First week on Agora")
        self.assertContains(response, "Start the discussion")

    def test_for_you_feed_marks_challenge_entries_in_the_feed(self):
        challenge = self.community.challenges.create(
            title="Prompt sprint",
            prompt_md="Ship one thoughtful post.",
            starts_at=timezone.now() - timezone.timedelta(hours=1),
            ends_at=timezone.now() + timezone.timedelta(days=2),
            is_featured=True,
            created_by=self.user,
        )
        challenge_post = Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="Challenge thread",
            body_md="Entry",
            score=2,
            hot_score=2,
            challenge=challenge,
        )
        self.community.memberships.create(user=self.user, role=CommunityMembership.Role.MEMBER)
        challenge.participations.create(user=self.user)
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        posts = list(response.context["posts"])
        matching = next(post for post in posts if post.id == challenge_post.id)
        self.assertTrue(matching.feed_reason)
        self.assertEqual(matching.challenge_id, challenge.id)
        self.assertContains(response, "Challenge entry")
