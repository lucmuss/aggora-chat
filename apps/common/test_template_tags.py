import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.communities.models import Community
from apps.common.templatetags.common_tags import contains, get_item, pairs, split, timesince_compact as common_timesince
from apps.posts.models import Post
from apps.posts.templatetags.post_tags import display_score, timesince_compact as post_timesince


User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "tag_user"),
        "email": overrides.pop("email", "tag_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "tag_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


@pytest.mark.django_db
class TestTemplateTags:
    def test_common_filters_cover_basic_edge_cases(self):
        assert get_item({"a": 1}, "a") == 1
        assert get_item({}, "missing") == 0
        assert split("a,b,c", ",") == ["a", "b", "c"]
        assert contains(["a", "b"], "a") is True
        assert contains([], "a") is False
        assert list(pairs(["a", "b", "c", "d"])) == [("a", "b"), ("c", "d")]

    def test_common_timesince_compact_formats_expected_ranges(self):
        now = timezone.now()

        assert common_timesince(now - datetime.timedelta(seconds=30)) == "30s"
        assert common_timesince(now - datetime.timedelta(minutes=5)) == "5m"
        assert common_timesince(now - datetime.timedelta(hours=3)) == "3h"
        assert common_timesince(now - datetime.timedelta(days=2)) == "2d"
        assert common_timesince(now - datetime.timedelta(days=800)) == "2y"
        assert common_timesince("not-a-datetime") == ""

    def test_post_display_score_hides_votes_inside_vote_hide_window(self):
        user = make_user()
        community = Community.objects.create(
            name="Tag Community",
            slug="tag-community",
            title="Tag Community",
            description="Template tag tests",
            creator=user,
            vote_hide_minutes=60,
        )
        hidden_post = Post.objects.create(
            community=community,
            author=user,
            post_type=Post.PostType.TEXT,
            title="Hidden score",
            body_md="Body",
            score=9,
        )
        visible_post = Post.objects.create(
            community=community,
            author=user,
            post_type=Post.PostType.TEXT,
            title="Visible score",
            body_md="Body",
            score=7,
        )
        visible_post.created_at = timezone.now() - datetime.timedelta(hours=2)

        assert display_score(hidden_post) == "•"
        assert display_score(visible_post) == 7

    def test_post_timesince_compact_formats_minutes_hours_and_days(self):
        now = timezone.now()

        assert post_timesince(now - datetime.timedelta(seconds=30)) == "1m"
        assert post_timesince(now - datetime.timedelta(minutes=20)) == "20m"
        assert post_timesince(now - datetime.timedelta(hours=4)) == "4h"
        assert post_timesince(now - datetime.timedelta(days=3)) == "3d"

