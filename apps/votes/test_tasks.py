import pytest
from django.contrib.auth import get_user_model

from apps.communities.models import Community
from apps.posts.models import Comment, Post
from apps.votes.models import Vote
from apps.votes.tasks import recalculate_comment_vote_totals, recalculate_karma, recalculate_post_vote_totals


User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "vote_task_user"),
        "email": overrides.pop("email", "vote_task_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "vote_task_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_post():
    author = make_user(username="vote_task_author", email="vote_task_author@example.com", handle="vote_task_author")
    community = Community.objects.create(
        name="Vote Tasks",
        slug="vote-tasks",
        title="Vote Tasks",
        description="Vote task tests",
        creator=author,
    )
    post = Post.objects.create(community=community, author=author, post_type="text", title="Thread", body_md="Body")
    return author, post


@pytest.mark.django_db
class TestVoteTasks:
    def test_recalculate_post_vote_totals_updates_score_and_hot_score(self):
        author, post = make_post()
        voter_a = make_user(username="voter_a", email="voter_a@example.com", handle="voter_a")
        voter_b = make_user(username="voter_b", email="voter_b@example.com", handle="voter_b")
        Vote.objects.create(user=voter_a, post=post, value=Vote.VoteType.UPVOTE)
        Vote.objects.create(user=voter_b, post=post, value=Vote.VoteType.DOWNVOTE)

        recalculate_post_vote_totals(post.id)
        post.refresh_from_db()

        assert post.upvote_count == 1
        assert post.downvote_count == 1
        assert post.score == 0
        assert isinstance(post.hot_score, float)

    def test_recalculate_comment_vote_totals_updates_counts(self):
        author, post = make_post()
        comment = Comment.objects.create(post=post, author=author, body_md="Reply", body_html="<p>Reply</p>")
        voter = make_user(username="comment_task_voter", email="comment_task_voter@example.com", handle="comment_task_voter")
        Vote.objects.create(user=voter, comment=comment, value=Vote.VoteType.UPVOTE)

        recalculate_comment_vote_totals(comment.id)
        comment.refresh_from_db()

        assert comment.upvote_count == 1
        assert comment.downvote_count == 0
        assert comment.score == 1

    def test_recalculate_karma_updates_post_and_comment_karma(self):
        author, post = make_post()
        comment = Comment.objects.create(post=post, author=author, body_md="Reply", body_html="<p>Reply</p>")
        voter = make_user(username="karma_voter", email="karma_voter@example.com", handle="karma_voter")
        Vote.objects.create(user=voter, post=post, value=Vote.VoteType.UPVOTE)
        Vote.objects.create(user=voter, comment=comment, value=Vote.VoteType.DOWNVOTE)

        recalculate_karma(author.id)
        author.refresh_from_db()

        assert author.post_karma == 1
        assert author.comment_karma == -1
