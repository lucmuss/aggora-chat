import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.communities.models import Community
from apps.posts.models import Comment, Poll, PollOption, PollVote, Post

User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "post_model_user"),
        "email": overrides.pop("email", "post_model_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "post_model_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="post-models", creator=None):
    creator = creator or make_user(username=f"{slug}_creator", email=f"{slug}_creator@example.com", handle=f"{slug}_creator")
    return Community.objects.create(
        name=slug.replace("-", " ").title(),
        slug=slug,
        title=slug.replace("-", " ").title(),
        description="Post model tests",
        creator=creator,
    )


@pytest.mark.django_db
class TestPostModel:
    def test_visible_queryset_excludes_removed_posts(self):
        community = make_community("visible-posts")
        visible = Post.objects.create(community=community, author=community.creator, post_type="text", title="Visible", body_md="Body")
        Post.objects.create(
            community=community,
            author=community.creator,
            post_type="text",
            title="Removed",
            body_md="Body",
            is_removed=True,
        )

        assert list(Post.objects.visible().values_list("id", flat=True)) == [visible.id]

    def test_for_listing_selects_related_objects(self):
        community = make_community("for-listing")
        post = Post.objects.create(community=community, author=community.creator, post_type="text", title="Listed", body_md="Body")

        loaded = Post.objects.for_listing().get(pk=post.pk)

        assert loaded.community == community
        assert loaded.author == community.creator

    def test_post_save_generates_slug_and_renders_markdown(self):
        community = make_community("slug-save")
        post = Post(community=community, author=community.creator, post_type="text", title="Hello Agora", body_md="**Bold**")

        post.save()

        assert post.slug.startswith("hello-agora")
        assert "<strong>Bold</strong>" in post.body_html

    def test_post_str_returns_title(self):
        community = make_community("string-post")
        post = Post.objects.create(community=community, author=community.creator, post_type="text", title="Readable", body_md="Body")

        assert str(post) == "Readable"

    def test_post_defaults_are_initialized(self):
        community = make_community("defaults-post")
        post = Post.objects.create(community=community, author=community.creator, post_type="text", title="Defaults", body_md="Body")

        assert post.score == 0
        assert post.hot_score == 0.0
        assert post.is_spoiler is False
        assert post.is_nsfw is False
        assert post.is_locked is False
        assert post.is_stickied is False
        assert post.is_removed is False


@pytest.mark.django_db
class TestPollModels:
    def test_poll_is_open_when_no_close_time_and_false_after_end(self):
        community = make_community("poll-open")
        post = Post.objects.create(community=community, author=community.creator, post_type="poll", title="Poll", body_md="")
        open_poll = Poll.objects.create(post=post, closes_at=None)
        closed_poll = Poll.objects.create(
            post=Post.objects.create(community=community, author=community.creator, post_type="poll", title="Closed", body_md=""),
            closes_at=timezone.now() - timezone.timedelta(hours=1),
        )

        assert open_poll.is_open() is True
        assert closed_poll.is_open() is False

    def test_poll_option_ordering_uses_position_then_id(self):
        community = make_community("poll-option")
        poll = Poll.objects.create(
            post=Post.objects.create(community=community, author=community.creator, post_type="poll", title="Poll", body_md="")
        )
        second = PollOption.objects.create(poll=poll, label="Second", position=2)
        first = PollOption.objects.create(poll=poll, label="First", position=1)

        assert list(PollOption.objects.values_list("id", flat=True)[:2]) == [first.id, second.id]

    def test_poll_vote_unique_together_prevents_duplicate_user_vote(self):
        community = make_community("poll-vote")
        voter = make_user(username="pollvoter", email="pollvoter@example.com", handle="pollvoter")
        poll = Poll.objects.create(
            post=Post.objects.create(community=community, author=community.creator, post_type="poll", title="Poll", body_md="")
        )
        option = PollOption.objects.create(poll=poll, label="A", position=1)
        PollVote.objects.create(poll=poll, option=option, user=voter)

        with pytest.raises(IntegrityError):
            PollVote.objects.create(poll=poll, option=option, user=voter)


@pytest.mark.django_db
class TestCommentModel:
    def test_comment_save_renders_markdown(self):
        community = make_community("comment-render")
        post = Post.objects.create(community=community, author=community.creator, post_type="text", title="Thread", body_md="Body")
        comment = Comment(post=post, author=community.creator, body_md="**Reply**")

        comment.save()

        assert "<strong>Reply</strong>" in comment.body_html

    def test_comment_str_uses_pk_and_post_id(self):
        community = make_community("comment-str")
        post = Post.objects.create(community=community, author=community.creator, post_type="text", title="Thread", body_md="Body")
        comment = Comment.objects.create(post=post, author=community.creator, body_md="Reply", body_html="<p>Reply</p>")

        assert str(comment) == f"Comment {comment.pk} on {post.id}"
