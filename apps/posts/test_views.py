import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.communities.models import Community, CommunityMembership
from apps.moderation.models import Ban
from apps.posts.models import Poll, PollOption, Post

User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "post_view_user"),
        "email": overrides.pop("email", "post_view_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "post_view_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="post-view-community", creator=None, **overrides):
    creator = creator or make_user(username=f"{slug}_creator", email=f"{slug}_creator@example.com", handle=f"{slug}_creator")
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "Post view tests",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestPostViews:
    def test_create_post_redirects_anonymous_to_login(self, client):
        community = make_community("anon-create")

        response = client.get(reverse("create_post", kwargs={"community_slug": community.slug}))

        assert response.status_code == 302
        assert reverse("account_login") in response.url

    def test_create_post_invalid_data_rerenders_form(self, client):
        user = make_user(username="invalid_poster", email="invalid_poster@example.com", handle="invalid_poster")
        community = make_community("invalid-create", creator=user)
        client.force_login(user)

        response = client.post(reverse("create_post", kwargs={"community_slug": community.slug}), {"post_type": "text", "title": "Thread", "body_md": ""})

        assert response.status_code == 200
        assert response.context["form"].errors

    def test_create_post_rejects_banned_user(self, client):
        user = make_user(username="banned_poster", email="banned_poster@example.com", handle="banned_poster")
        community = make_community("banned-create", creator=user)
        Ban.objects.create(community=community, user=user, banned_by=user, reason="No posts", is_permanent=True)
        client.force_login(user)

        response = client.post(reverse("create_post", kwargs={"community_slug": community.slug}), {"post_type": "text", "title": "Thread", "body_md": "Body"})

        assert response.status_code == 403

    def test_create_post_crosspost_without_parent_returns_400(self, client):
        user = make_user(username="crossposter", email="crossposter@example.com", handle="crossposter")
        community = make_community("crosspost-400", creator=user)
        client.force_login(user)

        response = client.post(
            reverse("create_post", kwargs={"community_slug": community.slug}),
            {"post_type": "crosspost", "title": "Cross", "body_md": "Body"},
        )

        assert response.status_code == 400

    def test_post_detail_for_private_community_returns_403(self, client):
        owner = make_user(username="private_owner", email="private_owner@example.com", handle="private_owner")
        community = make_community("private-detail", creator=owner, community_type=Community.CommunityType.PRIVATE)
        post = Post.objects.create(community=community, author=owner, post_type="text", title="Private", body_md="Body")

        response = client.get(reverse("post_detail", kwargs={"community_slug": community.slug, "post_id": post.id, "slug": post.slug}))

        assert response.status_code == 403

    def test_post_detail_sets_joined_and_reply_flags(self, client):
        user = make_user(username="detail_user", email="detail_user@example.com", handle="detail_user")
        community = make_community("detail-flags", creator=user)
        CommunityMembership.objects.create(user=user, community=community)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Thread", body_md="Body")
        client.force_login(user)

        response = client.get(
            reverse("post_detail", kwargs={"community_slug": community.slug, "post_id": post.id, "slug": post.slug}),
            {"reply": "1", "welcome": "1"},
        )

        assert response.status_code == 200
        assert response.context["joined"] is True
        assert response.context["onboarding_reply_prompt"] is True
        assert response.context["welcome_prompt"] is True

    def test_create_comment_requires_body(self, client):
        user = make_user(username="comment_empty", email="comment_empty@example.com", handle="comment_empty")
        community = make_community("comment-empty", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Thread", body_md="Body")
        client.force_login(user)

        response = client.post(reverse("create_comment", kwargs={"post_id": post.id}), {"body_md": ""})

        assert response.status_code == 400

    def test_create_comment_htmx_returns_partial(self, client):
        user = make_user(username="comment_htmx", email="comment_htmx@example.com", handle="comment_htmx")
        community = make_community("comment-htmx", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Thread", body_md="Body")
        client.force_login(user)

        response = client.post(
            reverse("create_comment", kwargs={"post_id": post.id}),
            {"body_md": "Reply"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert "comment-" in response.content.decode()

    def test_create_comment_rejects_banned_user(self, client):
        user = make_user(username="comment_banned", email="comment_banned@example.com", handle="comment_banned")
        community = make_community("comment-banned", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Thread", body_md="Body")
        Ban.objects.create(community=community, user=user, banned_by=user, reason="No comments", is_permanent=True)
        client.force_login(user)

        response = client.post(reverse("create_comment", kwargs={"post_id": post.id}), {"body_md": "Reply"})

        assert response.status_code == 403

    def test_vote_poll_rejects_closed_poll(self, client):
        user = make_user(username="poll_closed", email="poll_closed@example.com", handle="poll_closed")
        community = make_community("poll-closed", creator=user)
        post = Post.objects.create(community=community, author=user, post_type=Post.PostType.POLL, title="Poll", body_md="")
        poll = Poll.objects.create(post=post, closes_at=timezone.now() - timezone.timedelta(minutes=1))
        option = PollOption.objects.create(poll=poll, label="A", position=1)
        CommunityMembership.objects.create(user=user, community=community)
        client.force_login(user)

        response = client.post(reverse("vote_poll", kwargs={"post_id": post.id}), {"option_id": option.id})

        assert response.status_code == 403

    def test_vote_poll_requires_membership_in_restricted_community(self, client):
        user = make_user(username="poll_restricted", email="poll_restricted@example.com", handle="poll_restricted")
        owner = make_user(username="poll_owner", email="poll_owner@example.com", handle="poll_owner")
        community = make_community("poll-restricted", creator=owner, community_type=Community.CommunityType.RESTRICTED)
        post = Post.objects.create(community=community, author=owner, post_type=Post.PostType.POLL, title="Poll", body_md="")
        poll = Poll.objects.create(post=post)
        option = PollOption.objects.create(poll=poll, label="A", position=1)
        client.force_login(user)

        response = client.post(reverse("vote_poll", kwargs={"post_id": post.id}), {"option_id": option.id})

        assert response.status_code == 403

    def test_create_post_supports_image_upload(self, client):
        user = make_user(username="image_uploader", email="image_uploader@example.com", handle="image_uploader")
        community = make_community("image-upload", creator=user)
        client.force_login(user)
        image = SimpleUploadedFile(
            "test.gif",
            (
                b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
                b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
                b"\x00\x02\x02D\x01\x00;"
            ),
            content_type="image/gif",
        )

        response = client.post(
            reverse("create_post", kwargs={"community_slug": community.slug}),
            {"post_type": "image", "title": "Image", "image": image},
        )

        assert response.status_code == 302
        assert Post.objects.filter(title="Image", post_type="image").exists()
