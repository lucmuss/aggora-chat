import pytest
from django.contrib.auth import get_user_model
from django.db.models import Value
from django.utils import timezone

from apps.accounts.models import Notification
from apps.communities.models import Community, CommunityChallenge, CommunityMembership
from apps.posts.models import Comment, Poll, PollOption, PollVote, Post
from apps.posts.services import (
    annotate_posts_with_user_state,
    apply_personalized_post_sort,
    apply_post_sort,
    build_comment_tree,
    create_reengagement_notifications,
    hot_score,
    pg_feed_queryset,
    share_links_for_post,
    submit_comment,
    submit_poll_vote,
    submit_post,
)
from apps.votes.models import SavedPost, Vote


User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "post_service_user"),
        "email": overrides.pop("email", "post_service_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "post_service_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="post-service-community", creator=None, **overrides):
    creator = creator or make_user(username=f"{slug}_creator", email=f"{slug}_creator@example.com", handle=f"{slug}_creator")
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "Post service tests",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestPostServices:
    def test_hot_score_returns_distinct_values_for_positive_negative_and_zero(self):
        created_at = timezone.now()

        positive = hot_score(10, 1, created_at)
        zero = hot_score(1, 1, created_at)
        negative = hot_score(1, 5, created_at)

        assert positive > zero
        assert negative < zero

    def test_submit_post_creates_poll_crosspost_and_self_vote(self):
        author = make_user(username="author_service", email="author_service@example.com", handle="author_service")
        community = make_community("submit-post", creator=author)
        original = Post.objects.create(community=community, author=author, post_type="text", title="Original", body_md="Body")

        poll_post = submit_post(
            author,
            community,
            {"post_type": Post.PostType.POLL, "title": "Poll thread", "body_md": "", "url": "", "image": None, "flair": None},
            poll_lines=["Alpha", "Beta"],
        )
        crosspost = submit_post(
            author,
            community,
            {"post_type": Post.PostType.CROSSPOST, "title": "Crosspost", "body_md": "Boost", "url": "", "image": None, "flair": None},
            crosspost_source_id=str(original.id),
        )

        assert poll_post.poll.options.count() == 2
        assert crosspost.crosspost_parent == original
        assert Vote.objects.filter(post=poll_post, user=author, value=Vote.VoteType.UPVOTE).count() == 1
        assert poll_post.score == 1
        assert poll_post.hot_score > 0

    def test_submit_comment_creates_comment_updates_counts_and_enforces_depth(self):
        author = make_user(username="comment_author", email="comment_author@example.com", handle="comment_author")
        replier = make_user(username="comment_replier", email="comment_replier@example.com", handle="comment_replier")
        community = make_community("submit-comment", creator=author)
        post = Post.objects.create(community=community, author=author, post_type="text", title="Thread", body_md="Body")
        parent = submit_comment(replier, post, "Level 1")
        current = parent
        for depth in range(2, 12):
            current = Comment.objects.create(post=post, parent=current, author=replier, body_md=f"Level {depth}", body_html=f"<p>{depth}</p>", depth=depth - 1)

        comment = submit_comment(replier, post, "Reply", parent_id=str(parent.id))
        post.refresh_from_db()

        assert comment.parent == parent
        assert comment.score == 1
        assert post.comment_count >= 2

        with pytest.raises(ValueError):
            submit_comment(replier, post, "Too deep", parent_id=str(current.id))

    def test_submit_poll_vote_rejects_closed_poll_and_updates_existing_vote(self):
        user = make_user(username="poll_user", email="poll_user@example.com", handle="poll_user")
        community = make_community("poll-vote-service", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="poll", title="Poll", body_md="")
        poll = Poll.objects.create(post=post)
        option_a = PollOption.objects.create(poll=poll, label="A", position=1)
        option_b = PollOption.objects.create(poll=poll, label="B", position=2)

        submit_poll_vote(user, poll, str(option_a.id))
        submit_poll_vote(user, poll, str(option_b.id))

        assert PollVote.objects.get(poll=poll, user=user).option == option_b

        poll.closes_at = timezone.now() - timezone.timedelta(minutes=1)
        poll.save(update_fields=["closes_at"])
        with pytest.raises(ValueError):
            submit_poll_vote(user, poll, str(option_a.id))

    def test_build_comment_tree_sorts_and_excludes_blocked_authors(self):
        owner = make_user(username="tree_owner", email="tree_owner@example.com", handle="tree_owner")
        blocked = make_user(username="tree_blocked", email="tree_blocked@example.com", handle="tree_blocked")
        viewer = make_user(username="tree_viewer", email="tree_viewer@example.com", handle="tree_viewer")
        viewer.blocked_users.add(blocked)
        community = make_community("comment-tree", creator=owner)
        post = Post.objects.create(community=community, author=owner, post_type="text", title="Thread", body_md="Body")
        visible = Comment.objects.create(post=post, author=owner, body_md="Visible", body_html="<p>Visible</p>", score=5)
        Comment.objects.create(post=post, author=blocked, body_md="Blocked", body_html="<p>Blocked</p>", score=9)
        Comment.objects.create(post=post, parent=visible, author=owner, body_md="Child", body_html="<p>Child</p>", score=1)

        comments = build_comment_tree(post, sort="top", user=viewer)

        assert [comment.body_md for comment in comments] == ["Visible"]
        assert comments[0].children[0].body_md == "Child"

    def test_annotate_posts_with_user_state_returns_votes_and_saved_ids(self):
        user = make_user(username="annotator", email="annotator@example.com", handle="annotator")
        community = make_community("annotate-posts", creator=user)
        first = Post.objects.create(community=community, author=user, post_type="text", title="First", body_md="Body")
        second = Post.objects.create(community=community, author=user, post_type="text", title="Second", body_md="Body")
        Vote.objects.create(user=user, post=first, value=Vote.VoteType.UPVOTE)
        SavedPost.objects.create(user=user, post=second)

        votes, saved = annotate_posts_with_user_state([first, second], user)

        assert votes == {first.id: 1}
        assert saved == {second.id}

    def test_apply_sort_helpers_and_personalized_feed_queryset(self):
        user = make_user(username="feed_user", email="feed_user@example.com", handle="feed_user")
        followed = make_user(username="feed_followed", email="feed_followed@example.com", handle="feed_followed")
        other = make_user(username="feed_other", email="feed_other@example.com", handle="feed_other")
        community = make_community("feed-sort", creator=user)
        joined = make_community("feed-joined", creator=user)
        CommunityMembership.objects.create(user=user, community=joined)
        user.followed_users.add(followed)
        CommunityChallenge.objects.create(
            community=community,
            title="Challenge",
            prompt_md="Prompt",
            starts_at=timezone.now() - timezone.timedelta(hours=1),
            ends_at=timezone.now() + timezone.timedelta(hours=1),
        )
        followed_post = Post.objects.create(community=community, author=followed, post_type="text", title="Followed", body_md="Body", score=1, hot_score=1)
        joined_post = Post.objects.create(community=joined, author=other, post_type="text", title="Joined", body_md="Body", score=2, hot_score=2)
        other_post = Post.objects.create(community=community, author=other, post_type="text", title="Other", body_md="Body", score=10, hot_score=10)
        Vote.objects.create(user=user, post=other_post, value=Vote.VoteType.UPVOTE)
        SavedPost.objects.create(user=user, post=other_post)

        sorted_basic = list(apply_post_sort(Post.objects.all(), sort="top"))
        personalized = list(pg_feed_queryset(user, scope="all"))
        communities_scope = list(pg_feed_queryset(user, scope="communities"))
        following_scope = list(pg_feed_queryset(user, scope="following"))
        manual_personalized = list(apply_personalized_post_sort(Post.objects.all().annotate(personal_boost=Value(1)), sort="hot"))

        assert sorted_basic[0] == other_post
        assert personalized[0] == followed_post
        assert joined_post in communities_scope
        assert followed_post in following_scope and joined_post not in following_scope
        assert manual_personalized

    def test_create_reengagement_notifications_respects_reply_preferences(self):
        post_author = make_user(username="notify_post", email="notify_post@example.com", handle="notify_post")
        parent_author = make_user(username="notify_parent", email="notify_parent@example.com", handle="notify_parent", notify_on_replies=False)
        replier = make_user(username="notify_replier", email="notify_replier@example.com", handle="notify_replier")
        community = make_community("reengage", creator=post_author)
        post = Post.objects.create(community=community, author=post_author, post_type="text", title="Thread", body_md="Body")
        parent = Comment.objects.create(post=post, author=parent_author, body_md="Parent", body_html="<p>Parent</p>")
        reply = Comment.objects.create(post=post, parent=parent, author=replier, body_md="Reply", body_html="<p>Reply</p>")

        create_reengagement_notifications(reply)

        assert Notification.objects.filter(user=post_author, notification_type=Notification.NotificationType.POST_REPLY).count() == 1
        assert Notification.objects.filter(user=parent_author, notification_type=Notification.NotificationType.COMMENT_REPLY).count() == 0

    def test_share_links_for_post_use_public_base_url_when_present(self, settings):
        settings.APP_NAME = "Agora"
        settings.APP_PUBLIC_URL = "https://aggora.example"
        user = make_user(username="share_post", email="share_post@example.com", handle="share_post")
        community = make_community("share-post", creator=user)
        post = Post.objects.create(community=community, author=user, post_type="text", title="Share Me", body_md="Body")

        links = share_links_for_post(post)

        assert links["copy_url"] == f"https://aggora.example/c/{community.slug}/post/{post.id}/{post.slug}/"
        assert "twitter.com" in links["x"]
