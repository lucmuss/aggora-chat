import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Notification
from apps.communities.models import Community, CommunityChallenge, CommunityMembership
from apps.moderation.models import Ban
from apps.posts.models import Comment, Poll, PollOption, Post

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

    def test_post_detail_renders_rich_markdown_comment_composer(self, client):
        user = make_user(username="comment_editor", email="comment_editor@example.com", handle="comment_editor")
        community = make_community("comment-editor", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Thread", body_md="Body")
        client.force_login(user)

        response = client.get(reverse("post_detail", kwargs={"community_slug": community.slug, "post_id": post.id, "slug": post.slug}))

        assert response.status_code == 200
        assert 'data-rich-markdown="true"' in response.content.decode()
        assert "Comment preview" in response.content.decode()
        assert 'data-mentions-url="' in response.content.decode()

    def test_create_comment_requires_body(self, client):
        user = make_user(username="comment_empty", email="comment_empty@example.com", handle="comment_empty")
        community = make_community("comment-empty", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Thread", body_md="Body")
        client.force_login(user)

        response = client.post(reverse("create_comment", kwargs={"post_id": post.id}), {"body_md": ""})

        assert response.status_code == 200
        assert "Comment body is required." in response.content.decode()
        assert Comment.objects.filter(post=post).count() == 0

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

    def test_post_detail_renders_reply_form_for_signed_in_users(self, client):
        user = make_user(username="reply_form_user", email="reply_form_user@example.com", handle="reply_form_user")
        community = make_community("reply-form", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Thread", body_md="Body")
        Comment.objects.create(post=post, author=user, body_md="Parent comment", body_html="<p>Parent comment</p>")
        client.force_login(user)

        response = client.get(reverse("post_detail", kwargs={"community_slug": community.slug, "post_id": post.id, "slug": post.slug}))

        assert response.status_code == 200
        assert "Post reply" in response.content.decode()
        assert 'name="parent_id"' in response.content.decode()

    def test_post_detail_renders_report_and_award_actions(self, client):
        user = make_user(username="report_award_ui", email="report_award_ui@example.com", handle="report_award_ui")
        other = make_user(username="report_award_other", email="report_award_other@example.com", handle="report_award_other")
        community = make_community("report-award-ui", creator=other)
        post = Post.objects.create(community=community, author=other, post_type="text", title="Thread", body_md="Body")
        Comment.objects.create(post=post, author=other, body_md="Parent comment", body_html="<p>Parent comment</p>")
        client.force_login(user)

        response = client.get(reverse("post_detail", kwargs={"community_slug": community.slug, "post_id": post.id, "slug": post.slug}))
        content = response.content.decode()

        assert response.status_code == 200
        assert "Send report" in content
        assert "Award" in content
        assert "You have 3 of 3 highlights left this month." in content

    def test_create_comment_supports_nested_reply(self, client):
        user = make_user(username="nested_reply_user", email="nested_reply_user@example.com", handle="nested_reply_user")
        community = make_community("nested-reply", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Thread", body_md="Body")
        parent = Comment.objects.create(post=post, author=user, body_md="Parent", body_html="<p>Parent</p>")
        client.force_login(user)

        response = client.post(
            reverse("create_comment", kwargs={"post_id": post.id}),
            {"body_md": "Child reply", "parent_id": str(parent.id)},
        )

        assert response.status_code == 302
        child = Comment.objects.get(body_md="Child reply")
        assert child.parent_id == parent.id

    def test_create_comment_creates_mention_notification(self, client):
        author = make_user(username="mention_author", email="mention_author@example.com", handle="mention_author")
        mentioned = make_user(username="ariane", email="mention_target@example.com", handle="ariane")
        community = make_community("mention-comment", creator=author)
        post = Post.objects.create(community=community, author=author, post_type="text", title="Thread", body_md="Body")
        client.force_login(author)

        response = client.post(reverse("create_comment", kwargs={"post_id": post.id}), {"body_md": "Hey @ariane"})

        assert response.status_code == 302
        notification = Notification.objects.get(user=mentioned, notification_type=Notification.NotificationType.MENTION)
        assert "mentioned you in a comment" in notification.message
        assert f"#comment-" in notification.url

    def test_create_post_creates_mention_notification(self, client):
        author = make_user(username="mention_post_author", email="mention_post_author@example.com", handle="mention_post_author")
        mentioned = make_user(username="ariane_post", email="mention_post_target@example.com", handle="ariane_post")
        community = make_community("mention-post", creator=author)
        client.force_login(author)

        response = client.post(
            reverse("create_post", kwargs={"community_slug": community.slug}),
            {"post_type": "text", "title": "Calling @ariane_post", "body_md": "Join this thread"},
        )

        assert response.status_code == 302
        notification = Notification.objects.get(user=mentioned, notification_type=Notification.NotificationType.MENTION)
        assert "mentioned you in a thread" in notification.message

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

    def test_create_post_can_attach_active_challenge_entry(self, client):
        user = make_user(username="challenge_entry_author", email="challenge_entry_author@example.com", handle="challenge_entry_author")
        community = make_community("challenge-entry-create", creator=user)
        challenge = CommunityChallenge.objects.create(
            community=community,
            title="Prompt of the week",
            prompt_md="Show your process.",
            starts_at=timezone.now() - timezone.timedelta(hours=1),
            ends_at=timezone.now() + timezone.timedelta(days=2),
            is_featured=True,
            created_by=user,
        )
        client.force_login(user)

        response = client.post(
            reverse("create_post", kwargs={"community_slug": community.slug}),
            {
                "post_type": "text",
                "title": "Challenge entry",
                "body_md": "Here is my take.",
                "challenge": str(challenge.id),
            },
        )

        assert response.status_code == 302
        created = Post.objects.get(title="Challenge entry")
        assert created.challenge_id == challenge.id

    def test_author_can_soft_delete_and_restore_post(self, client):
        user = make_user(username="delete_post_author", email="delete_post_author@example.com", handle="delete_post_author")
        community = make_community("delete-post-community", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Delete me", body_md="Body")
        client.force_login(user)

        delete_response = client.post(reverse("delete_post", kwargs={"post_id": post.id}))
        assert delete_response.status_code == 302
        post.refresh_from_db()
        assert post.author_deleted_at is not None

        restore_response = client.post(reverse("restore_deleted_post", kwargs={"post_id": post.id}))
        post.refresh_from_db()
        assert restore_response.status_code == 302
        assert post.author_deleted_at is None

    def test_author_can_soft_delete_and_restore_comment(self, client):
        user = make_user(username="delete_comment_author", email="delete_comment_author@example.com", handle="delete_comment_author")
        community = make_community("delete-comment-community", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Thread", body_md="Body")
        comment = Comment.objects.create(post=post, author=user, body_md="Comment", body_html="<p>Comment</p>")
        client.force_login(user)

        delete_response = client.post(reverse("delete_comment", kwargs={"comment_id": comment.id}))
        comment.refresh_from_db()
        assert delete_response.status_code == 302
        assert comment.author_deleted_at is not None

        restore_response = client.post(reverse("restore_deleted_comment", kwargs={"comment_id": comment.id}))
        comment.refresh_from_db()
        assert restore_response.status_code == 302
        assert comment.author_deleted_at is None
