from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.communities.models import Community
from apps.posts.models import Post

from apps.votes.models import SavedPost, Vote

User = get_user_model()


class VoteFlowTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author",
            email="author@example.com",
            password="password123",
            handle="author",
        )
        self.voter = User.objects.create_user(
            username="voter",
            email="voter@example.com",
            password="password123",
            handle="voter",
        )
        self.community = Community.objects.create(
            name="Agora Votes",
            slug="agora-votes",
            title="Agora Votes",
            description="Voting tests.",
            creator=self.author,
        )
        self.post = Post.objects.create(
            community=self.community,
            author=self.author,
            post_type="text",
            title="Vote me",
            body_md="Body",
        )

    def test_vote_updates_post_score(self):
        self.client.force_login(self.voter)

        response = self.client.post(reverse("vote"), {"post_id": self.post.id, "value": "1"})

        self.post.refresh_from_db()
        self.author.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.post.score, 1)
        self.assertEqual(Vote.objects.filter(post=self.post, user=self.voter).count(), 1)
        self.assertEqual(self.author.post_karma, 1)

    def test_toggle_save_creates_saved_post(self):
        self.client.force_login(self.voter)

        response = self.client.post(reverse("toggle_save", kwargs={"post_id": self.post.id}))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(SavedPost.objects.filter(user=self.voter, post=self.post).exists())
