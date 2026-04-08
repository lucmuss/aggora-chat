import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.communities.models import Community
from apps.posts.models import Comment, Post
from apps.votes.models import ContentAward, SavedPost, Vote

User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "vote_model_user"),
        "email": overrides.pop("email", "vote_model_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "vote_model_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_post():
    author = make_user(username="vote_author", email="vote_author@example.com", handle="vote_author")
    community = Community.objects.create(
        name="Vote Models",
        slug="vote-models",
        title="Vote Models",
        description="Vote model tests",
        creator=author,
    )
    return Post.objects.create(community=community, author=author, post_type="text", title="Thread", body_md="Body")


@pytest.mark.django_db
class TestVoteModel:
    def test_unique_post_vote_per_user(self):
        voter = make_user(username="post_voter", email="post_voter@example.com", handle="post_voter")
        post = make_post()
        Vote.objects.create(user=voter, post=post, value=Vote.VoteType.UPVOTE)

        with pytest.raises(IntegrityError):
            Vote.objects.create(user=voter, post=post, value=Vote.VoteType.DOWNVOTE)

    def test_unique_comment_vote_per_user(self):
        voter = make_user(username="comment_voter", email="comment_voter@example.com", handle="comment_voter")
        post = make_post()
        comment = Comment.objects.create(post=post, author=post.author, body_md="Reply", body_html="<p>Reply</p>")
        Vote.objects.create(user=voter, comment=comment, value=Vote.VoteType.UPVOTE)

        with pytest.raises(IntegrityError):
            Vote.objects.create(user=voter, comment=comment, value=Vote.VoteType.DOWNVOTE)

    def test_check_constraint_rejects_both_targets(self):
        voter = make_user(username="check_voter", email="check_voter@example.com", handle="check_voter")
        post = make_post()
        comment = Comment.objects.create(post=post, author=post.author, body_md="Reply", body_html="<p>Reply</p>")

        with pytest.raises(IntegrityError):
            Vote.objects.create(user=voter, post=post, comment=comment, value=Vote.VoteType.UPVOTE)

    def test_check_constraint_rejects_missing_targets(self):
        voter = make_user(username="check_voter_none", email="check_voter_none@example.com", handle="check_voter_none")

        with pytest.raises(IntegrityError):
            Vote.objects.create(user=voter, value=Vote.VoteType.UPVOTE)


@pytest.mark.django_db
class TestSavedPostModel:
    def test_saved_post_unique_together(self):
        voter = make_user(username="saved_voter", email="saved_voter@example.com", handle="saved_voter")
        post = make_post()
        SavedPost.objects.create(user=voter, post=post)

        with pytest.raises(IntegrityError):
            SavedPost.objects.create(user=voter, post=post)

    def test_saved_post_defaults_to_unread_queue_status(self):
        voter = make_user(username="saved_status", email="saved_status@example.com", handle="saved_status")
        post = make_post()

        saved = SavedPost.objects.create(user=voter, post=post)

        assert saved.status == SavedPost.QueueStatus.UNREAD


@pytest.mark.django_db
class TestContentAwardModel:
    def test_remaining_for_user_defaults_to_three(self):
        giver = make_user(username="award_giver_default", email="award_giver_default@example.com", handle="award_giver_default")

        assert ContentAward.remaining_for_user(giver) == 3

    def test_awards_given_this_month_reduces_remaining_quota(self):
        giver = make_user(username="award_giver_quota", email="award_giver_quota@example.com", handle="award_giver_quota")
        recipient = make_user(username="award_recipient_quota", email="award_recipient_quota@example.com", handle="award_recipient_quota")
        post = make_post()
        other_post = Post.objects.create(community=post.community, author=recipient, post_type="text", title="Other", body_md="Body")
        comment = Comment.objects.create(post=post, author=recipient, body_md="Reply", body_html="<p>Reply</p>")

        ContentAward.objects.create(user=giver, recipient=recipient, post=post)
        ContentAward.objects.create(user=giver, recipient=recipient, post=other_post)
        ContentAward.objects.create(user=giver, recipient=recipient, comment=comment)

        assert ContentAward.awards_given_this_month(giver) == 3
        assert ContentAward.remaining_for_user(giver) == 0

    def test_award_unique_constraint_prevents_duplicate_post_awards(self):
        giver = make_user(username="award_dup_giver", email="award_dup_giver@example.com", handle="award_dup_giver")
        recipient = make_user(username="award_dup_recipient", email="award_dup_recipient@example.com", handle="award_dup_recipient")
        post = make_post()

        ContentAward.objects.create(user=giver, recipient=recipient, post=post)

        with pytest.raises(IntegrityError):
            ContentAward.objects.create(user=giver, recipient=recipient, post=post)
