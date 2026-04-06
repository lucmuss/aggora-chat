import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.communities.models import Community
from apps.posts.models import Comment, Post
from apps.votes.models import ContentAward, SavedPost, Vote

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
        assert 'vote-widget' in response.content.decode()
        assert 'comment_id' in response.content.decode()

    def test_vote_requires_login(self, client):
        author = make_user(username="anon_vote_author", email="anon_vote_author@example.com", handle="anon_vote_author")
        community = make_community("anon-vote", creator=author)
        post = Post.objects.create(community=community, author=author, post_type="text", title="Thread", body_md="Body")

        response = client.post(reverse("vote"), {"post_id": post.id, "value": "1"})

        assert response.status_code == 302
        assert reverse("account_login") in response.url

    def test_vote_requires_login_with_htmx_redirect_header(self, client):
        author = make_user(username="anon_htmx_vote_author", email="anon_htmx_vote_author@example.com", handle="anon_htmx_vote_author")
        community = make_community("anon-htmx-vote", creator=author)
        post = Post.objects.create(community=community, author=author, post_type="text", title="Thread", body_md="Body")

        response = client.post(
            reverse("vote"),
            {"post_id": post.id, "value": "1"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 204
        assert reverse("account_login") in response.headers["HX-Redirect"]

    def test_toggle_save_forbidden_for_private_community_post(self, client):
        owner = make_user(username="private_save_owner", email="private_save_owner@example.com", handle="private_save_owner")
        saver = make_user(username="private_saver", email="private_saver@example.com", handle="private_saver")
        community = make_community("private-save", creator=owner, community_type=Community.CommunityType.PRIVATE)
        post = Post.objects.create(community=community, author=owner, post_type="text", title="Thread", body_md="Body")
        client.force_login(saver)

        response = client.post(reverse("toggle_save", kwargs={"post_id": post.id}))

        assert response.status_code == 403
        assert SavedPost.objects.filter(user=saver, post=post).count() == 0

    def test_toggle_save_requires_login_with_htmx_redirect_header(self, client):
        owner = make_user(username="anon_save_owner", email="anon_save_owner@example.com", handle="anon_save_owner")
        community = make_community("anon-save", creator=owner)
        post = Post.objects.create(community=community, author=owner, post_type="text", title="Save me", body_md="Body")

        response = client.post(
            reverse("toggle_save", kwargs={"post_id": post.id}),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 204
        assert reverse("account_login") in response.headers["HX-Redirect"]

    def test_update_saved_post_status_moves_item_through_reader_queue(self, client):
        owner = make_user(username="queue_owner", email="queue_owner@example.com", handle="queue_owner")
        reader = make_user(username="queue_reader", email="queue_reader@example.com", handle="queue_reader")
        community = make_community("queue-community", creator=owner)
        post = Post.objects.create(community=community, author=owner, post_type="text", title="Queue me", body_md="Body")
        saved = SavedPost.objects.create(user=reader, post=post)
        client.force_login(reader)

        response = client.post(
            reverse("update_saved_post_status", kwargs={"post_id": post.id}),
            {"status": SavedPost.QueueStatus.READING},
        )

        assert response.status_code == 302
        saved.refresh_from_db()
        assert saved.status == SavedPost.QueueStatus.READING

    def test_update_saved_post_status_remove_action_deletes_queue_item(self, client):
        owner = make_user(username="queue_remove_owner", email="queue_remove_owner@example.com", handle="queue_remove_owner")
        reader = make_user(username="queue_remove_reader", email="queue_remove_reader@example.com", handle="queue_remove_reader")
        community = make_community("queue-remove", creator=owner)
        post = Post.objects.create(community=community, author=owner, post_type="text", title="Remove me", body_md="Body")
        SavedPost.objects.create(user=reader, post=post)
        client.force_login(reader)

        response = client.post(
            reverse("update_saved_post_status", kwargs={"post_id": post.id}),
            {"action": "remove"},
        )

        assert response.status_code == 302
        assert SavedPost.objects.filter(user=reader, post=post).count() == 0

    def test_give_award_to_post_increments_award_count(self, client):
        author = make_user(username="award_post_author", email="award_post_author@example.com", handle="award_post_author")
        giver = make_user(username="award_post_giver", email="award_post_giver@example.com", handle="award_post_giver")
        community = make_community("award-post", creator=author)
        post = Post.objects.create(community=community, author=author, post_type="text", title="Award me", body_md="Body")
        client.force_login(giver)

        response = client.post(reverse("give_award"), {"post_id": post.id, "next": "/"})

        assert response.status_code == 302
        post.refresh_from_db()
        assert post.award_count == 1
        assert ContentAward.objects.filter(user=giver, post=post).count() == 1

    def test_give_award_to_comment_respects_monthly_limit(self, client):
        author = make_user(username="award_comment_author", email="award_comment_author@example.com", handle="award_comment_author")
        giver = make_user(username="award_comment_giver", email="award_comment_giver@example.com", handle="award_comment_giver")
        community = make_community("award-comment", creator=author)
        post = Post.objects.create(community=community, author=author, post_type="text", title="Thread", body_md="Body")
        other_post = Post.objects.create(community=community, author=author, post_type="text", title="Second", body_md="Body")
        another_post = Post.objects.create(community=community, author=author, post_type="text", title="Third", body_md="Body")
        comment = Comment.objects.create(post=post, author=author, body_md="Reply", body_html="<p>Reply</p>")
        client.force_login(giver)

        client.post(reverse("give_award"), {"post_id": post.id, "next": "/"})
        client.post(reverse("give_award"), {"post_id": other_post.id, "next": "/"})
        client.post(reverse("give_award"), {"post_id": another_post.id, "next": "/"})
        response = client.post(reverse("give_award"), {"comment_id": comment.id, "next": "/"}, follow=True)

        comment.refresh_from_db()
        assert response.status_code == 200
        assert comment.award_count == 0
        assert "used all three awards" in response.content.decode()

    def test_give_award_requires_login_with_htmx_redirect_header(self, client):
        author = make_user(username="anon_award_author", email="anon_award_author@example.com", handle="anon_award_author")
        community = make_community("anon-award", creator=author)
        post = Post.objects.create(community=community, author=author, post_type="text", title="Award target", body_md="Body")

        response = client.post(reverse("give_award"), {"post_id": post.id}, HTTP_HX_REQUEST="true")

        assert response.status_code == 204
        assert reverse("account_login") in response.headers["HX-Redirect"]
