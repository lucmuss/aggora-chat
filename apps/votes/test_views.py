import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.communities.models import Community
from apps.posts.models import Comment, Post
from apps.votes.models import SavedPost, Vote


User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "vote_view_user"),
        "email": overrides.pop("email", "vote_view_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "vote_view_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="vote-view-community", creator=None, **overrides):
    creator = creator or make_user(username=f"{slug}_creator", email=f"{slug}_creator@example.com", handle=f"{slug}_creator")
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "Vote view tests",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestVoteViews:
    def test_vote_same_value_twice_removes_vote(self, client):
        author = make_user(username="vote_author_view", email="vote_author_view@example.com", handle="vote_author_view")
        voter = make_user(username="vote_twice", email="vote_twice@example.com", handle="vote_twice")
        community = make_community("vote-twice", creator=author)
        post = Post.objects.create(community=community, author=author, post_type="text", title="Thread", body_md="Body")
        client.force_login(voter)

        first = client.post(reverse("vote"), {"post_id": post.id, "value": "1"})
        second = client.post(reverse("vote"), {"post_id": post.id, "value": "1"})

        assert first.status_code == 200
        assert second.status_code == 200
        assert Vote.objects.filter(post=post, user=voter).count() == 0

    def test_vote_switches_from_upvote_to_downvote(self, client):
        author = make_user(username="vote_author_switch", email="vote_author_switch@example.com", handle="vote_author_switch")
        voter = make_user(username="vote_switch", email="vote_switch@example.com", handle="vote_switch")
        community = make_community("vote-switch", creator=author)
        post = Post.objects.create(community=community, author=author, post_type="text", title="Thread", body_md="Body")
        client.force_login(voter)

        client.post(reverse("vote"), {"post_id": post.id, "value": "1"})
        response = client.post(reverse("vote"), {"post_id": post.id, "value": "-1"})

        assert response.status_code == 200
        assert Vote.objects.get(post=post, user=voter).value == -1

    def test_vote_comment_path_creates_comment_vote(self, client):
        author = make_user(username="comment_vote_author", email="comment_vote_author@example.com", handle="comment_vote_author")
        voter = make_user(username="comment_vote_voter", email="comment_vote_voter@example.com", handle="comment_vote_voter")
        community = make_community("comment-vote", creator=author)
        post = Post.objects.create(community=community, author=author, post_type="text", title="Thread", body_md="Body")
        comment = Comment.objects.create(post=post, author=author, body_md="Reply", body_html="<p>Reply</p>")
        client.force_login(voter)

        response = client.post(reverse("vote"), {"comment_id": comment.id, "value": "1"})

        assert response.status_code == 200
        assert Vote.objects.filter(comment=comment, user=voter).count() == 1

    def test_vote_requires_login(self, client):
        author = make_user(username="anon_vote_author", email="anon_vote_author@example.com", handle="anon_vote_author")
        community = make_community("anon-vote", creator=author)
        post = Post.objects.create(community=community, author=author, post_type="text", title="Thread", body_md="Body")

        response = client.post(reverse("vote"), {"post_id": post.id, "value": "1"})

        assert response.status_code == 302
        assert reverse("account_login") in response.url

    def test_toggle_save_forbidden_for_private_community_post(self, client):
        owner = make_user(username="private_save_owner", email="private_save_owner@example.com", handle="private_save_owner")
        saver = make_user(username="private_saver", email="private_saver@example.com", handle="private_saver")
        community = make_community("private-save", creator=owner, community_type=Community.CommunityType.PRIVATE)
        post = Post.objects.create(community=community, author=owner, post_type="text", title="Thread", body_md="Body")
        client.force_login(saver)

        response = client.post(reverse("toggle_save", kwargs={"post_id": post.id}))

        assert response.status_code == 403
        assert SavedPost.objects.filter(user=saver, post=post).count() == 0
