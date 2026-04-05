from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.communities.models import Community
from apps.votes.models import Vote

from .models import Comment, Post

User = get_user_model()


class PostFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="poster",
            email="poster@example.com",
            password="password123",
            handle="poster",
        )
        self.community = Community.objects.create(
            name="Agora Posts",
            slug="agora-posts",
            title="Agora Posts",
            description="Posts and comments.",
            creator=self.user,
        )

    def test_create_text_post_auto_upvotes(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("create_post", kwargs={"community_slug": self.community.slug}),
            {"post_type": "text", "title": "First thread", "body_md": "Hello **Agora**"},
        )

        post = Post.objects.get()
        self.assertRedirects(
            response,
            reverse(
                "post_detail",
                kwargs={"community_slug": self.community.slug, "post_id": post.id, "slug": post.slug},
            ),
        )
        self.assertEqual(post.score, 1)
        self.assertEqual(Vote.objects.filter(post=post, value=1).count(), 1)

    def test_create_comment_updates_post_count(self):
        post = Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="Thread",
            body_md="Body",
        )
        self.client.force_login(self.user)

        response = self.client.post(reverse("create_comment", kwargs={"post_id": post.id}), {"body_md": "Comment"})

        post.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(post.comment_count, 1)

    def test_post_detail_includes_discussion_forum_posting_schema(self):
        post = Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="SEO thread",
            body_md="Body",
        )

        response = self.client.get(
            reverse(
                "post_detail",
                kwargs={"community_slug": self.community.slug, "post_id": post.id, "slug": post.slug},
            )
        )

        self.assertContains(response, '"DiscussionForumPosting"')
        self.assertContains(response, 'rel="canonical"')

    def test_home_feed_renders_post(self):
        Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="Visible thread",
            body_md="Body",
            score=5,
            hot_score=5,
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible thread")

    def test_create_image_post(self):
        self.client.force_login(self.user)
        image = SimpleUploadedFile(
            "test.gif",
            (
                b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
                b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
                b"\x00\x02\x02D\x01\x00;"
            ),
            content_type="image/gif",
        )

        response = self.client.post(
            reverse("create_post", kwargs={"community_slug": self.community.slug}),
            {"post_type": "image", "title": "Image thread", "image": image},
        )

        post = Post.objects.get(title="Image thread")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(post.post_type, "image")
        self.assertTrue(bool(post.image))

    def test_create_poll_post_and_vote(self):
        self.community.allow_polls = True
        self.community.save(update_fields=["allow_polls"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("create_post", kwargs={"community_slug": self.community.slug}),
            {
                "post_type": "poll",
                "title": "Choose one",
                "poll_option_lines": "Alpha\nBeta\nGamma",
            },
        )

        post = Post.objects.get(title="Choose one")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(post.post_type, "poll")
        self.assertEqual(post.poll.options.count(), 3)

        vote_response = self.client.post(
            reverse("vote_poll", kwargs={"post_id": post.id}),
            {"option_id": post.poll.options.first().id},
        )

        self.assertEqual(vote_response.status_code, 302)
        self.assertEqual(post.poll.votes.count(), 1)

    def test_create_crosspost(self):
        original = Post.objects.create(
            community=self.community,
            author=self.user,
            post_type="text",
            title="Original thread",
            body_md="Body",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("create_post", kwargs={"community_slug": self.community.slug}),
            {
                "post_type": "crosspost",
                "title": "Original thread",
                "body_md": "Signal boost",
                "crosspost_parent_id": original.id,
            },
        )

        crosspost = Post.objects.exclude(pk=original.pk).get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(crosspost.post_type, "crosspost")
        self.assertEqual(crosspost.crosspost_parent, original)
