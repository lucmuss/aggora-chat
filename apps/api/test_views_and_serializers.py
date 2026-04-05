import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import UserBadge
from apps.api.pagination import AgoraCursorPagination
from apps.api.serializers import CommentSerializer, PostDetailSerializer, UserProfileSerializer
from apps.communities.models import Community, CommunityMembership
from apps.posts.models import Comment, Poll, PollOption, Post
from apps.votes.models import Vote


User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "api_branch_user"),
        "email": overrides.pop("email", "api_branch_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "api_branch_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="api-branches", creator=None, **overrides):
    creator = creator or make_user(
        username=f"{slug}_creator",
        email=f"{slug}_creator@example.com",
        handle=f"{slug}_creator",
    )
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "API branch tests",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestApiSerializersAndViews:
    def setup_method(self):
        self.client = APIClient()
        self.user = make_user(username="api_owner", email="api_owner@example.com", handle="api_owner")
        self.community = make_community("api-views", creator=self.user)
        CommunityMembership.objects.create(user=self.user, community=self.community)
        self.post = Post.objects.create(
            community=self.community,
            author=self.user,
            post_type=Post.PostType.TEXT,
            title="API thread",
            body_md="Body",
        )
        self.token = Token.objects.create(user=self.user)

    def test_post_detail_serializer_handles_poll_and_image_fields(self):
        serializer = PostDetailSerializer(self.post)
        poll_post = Post.objects.create(
            community=self.community,
            author=self.user,
            post_type=Post.PostType.POLL,
            title="Poll thread",
            body_md="Vote",
        )
        poll = Poll.objects.create(post=poll_post)
        PollOption.objects.create(poll=poll, label="Alpha", position=1)
        PollOption.objects.create(poll=poll, label="Beta", position=2)
        poll_serializer = PostDetailSerializer(poll_post)

        assert serializer.data["poll"] is None
        assert serializer.data["image_url"] is None
        assert poll_serializer.data["poll"]["options"][0]["label"] == "Alpha"

    def test_comment_serializer_returns_nested_children_when_present(self):
        parent = Comment.objects.create(post=self.post, author=self.user, body_md="Parent", body_html="<p>Parent</p>")
        child = Comment.objects.create(
            post=self.post,
            parent=parent,
            author=self.user,
            body_md="Child",
            body_html="<p>Child</p>",
            depth=1,
        )
        parent.children = [child]

        data = CommentSerializer(parent).data

        assert data["replies"][0]["id"] == child.id

    def test_user_profile_serializer_returns_badges_and_avatar_url(self):
        UserBadge.objects.create(
            user=self.user,
            code="first_steps",
            title="First Steps",
            description="Started",
            icon="*",
        )

        data = UserProfileSerializer(self.user).data

        assert data["avatar_url"] is None
        assert data["badges"][0]["code"] == "first_steps"
        assert data["total_karma"] == self.user.total_karma()

    def test_cursor_pagination_response_uses_after_before_and_count(self):
        paginator = AgoraCursorPagination()
        paginator.get_next_link = lambda: "https://example.com/api?after=next"
        paginator.get_previous_link = lambda: "https://example.com/api?after=prev"

        response = paginator.get_paginated_response([{"id": 1}, {"id": 2}])

        assert response.data["after"] == "https://example.com/api?after=next"
        assert response.data["before"] == "https://example.com/api?after=prev"
        assert response.data["count"] == 2

    def test_post_comments_api_respects_private_community_visibility(self):
        self.community.community_type = Community.CommunityType.PRIVATE
        self.community.save(update_fields=["community_type"])

        response = self.client.get(reverse("api_post_comments", kwargs={"pk": self.post.id}))

        assert response.status_code == 403

    def test_post_detail_api_respects_private_community_visibility(self):
        self.community.community_type = Community.CommunityType.PRIVATE
        self.community.save(update_fields=["community_type"])

        response = self.client.get(reverse("api_post_detail", kwargs={"pk": self.post.id}))

        assert response.status_code == 403

    def test_comment_create_api_rejects_empty_body(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.client.post(
            reverse("api_comment_create"),
            {"post_id": self.post.id, "body_md": "   "},
            format="json",
        )

        assert response.status_code == 400
        assert "body_md" in response.data["errors"]

    def test_vote_api_returns_comment_payload_for_comment_vote(self):
        voter = make_user(username="api_voter", email="api_voter@example.com", handle="api_voter")
        token = Token.objects.create(user=voter)
        comment = Comment.objects.create(post=self.post, author=self.user, body_md="Reply", body_html="<p>Reply</p>")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post(
            reverse("api_vote"),
            {"comment_id": comment.id, "value": Vote.VoteType.UPVOTE},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["id"] == comment.id
        assert Vote.objects.filter(comment=comment, user=voter).count() == 1

    def test_poll_vote_api_rejects_closed_poll(self):
        poll_post = Post.objects.create(
            community=self.community,
            author=self.user,
            post_type=Post.PostType.POLL,
            title="Closed poll",
            body_md="Vote",
        )
        poll = Poll.objects.create(post=poll_post, closes_at=timezone.now() - timezone.timedelta(minutes=1))
        option = PollOption.objects.create(poll=poll, label="Alpha", position=1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.client.post(
            reverse("api_poll_vote", kwargs={"pk": poll_post.id}),
            {"option_id": option.id},
            format="json",
        )

        assert response.status_code == 403

    def test_search_api_forwards_post_type_and_media_filters(self):
        Post.objects.create(
            community=self.community,
            author=self.user,
            post_type=Post.PostType.LINK,
            title="Link only result",
            body_md="Body",
            url="https://example.com",
        )

        response = self.client.get(reverse("api_search"), {"q": "result", "post_type": "link", "media": "links"})

        assert response.status_code == 200
        assert [item["title"] for item in response.data["items"]] == ["Link only result"]
