import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.communities.models import Community, PostFlair
from apps.posts.forms import PostCreateForm
from apps.posts.models import Post


User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "post_form_user"),
        "email": overrides.pop("email", "post_form_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "post_form_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="post-form-community", creator=None, **overrides):
    creator = creator or make_user(username=f"{slug}_creator", email=f"{slug}_creator@example.com", handle=f"{slug}_creator")
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "Post form tests",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestPostCreateForm:
    def test_text_post_requires_body(self):
        community = make_community("text-body")
        form = PostCreateForm(data={"post_type": Post.PostType.TEXT, "title": "Thread", "body_md": ""}, community=community)

        assert form.is_valid() is False
        assert "body_md" in form.errors

    def test_link_post_requires_url(self):
        community = make_community("link-url")
        form = PostCreateForm(data={"post_type": Post.PostType.LINK, "title": "Thread", "url": ""}, community=community)

        assert form.is_valid() is False
        assert "url" in form.errors

    def test_image_post_requires_file(self):
        community = make_community("image-required")
        form = PostCreateForm(data={"post_type": Post.PostType.IMAGE, "title": "Thread"}, community=community)

        assert form.is_valid() is False
        assert "image" in form.errors

    def test_poll_requires_two_to_six_options(self):
        community = make_community("poll-count", allow_polls=True)
        too_few = PostCreateForm(
            data={"post_type": Post.PostType.POLL, "title": "Poll", "poll_option_lines": "One"},
            community=community,
        )
        too_many = PostCreateForm(
            data={"post_type": Post.PostType.POLL, "title": "Poll", "poll_option_lines": "1\n2\n3\n4\n5\n6\n7"},
            community=community,
        )

        assert too_few.is_valid() is False
        assert "poll_option_lines" in too_few.errors
        assert too_many.is_valid() is False
        assert "poll_option_lines" in too_many.errors

    def test_post_type_respects_community_capabilities(self):
        community = make_community(
            "disabled-types",
            allow_text_posts=False,
            allow_link_posts=False,
            allow_image_posts=False,
            allow_polls=False,
        )

        text_form = PostCreateForm(data={"post_type": "text", "title": "T", "body_md": "Body"}, community=community)
        link_form = PostCreateForm(data={"post_type": "link", "title": "T", "url": "https://example.com"}, community=community)
        image = SimpleUploadedFile("image.gif", b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;", content_type="image/gif")
        image_form = PostCreateForm(data={"post_type": "image", "title": "T"}, files={"image": image}, community=community)
        poll_form = PostCreateForm(data={"post_type": "poll", "title": "P", "poll_option_lines": "A\nB"}, community=community)

        assert text_form.is_valid() is False and "post_type" in text_form.errors
        assert link_form.is_valid() is False and "post_type" in link_form.errors
        assert image_form.is_valid() is False and "post_type" in image_form.errors
        assert poll_form.is_valid() is False and "post_type" in poll_form.errors

    def test_requires_flair_when_community_demands_it(self):
        community = make_community("required-flair", require_post_flair=True)
        form = PostCreateForm(
            data={"post_type": Post.PostType.TEXT, "title": "Thread", "body_md": "Body"},
            community=community,
        )

        assert form.is_valid() is False
        assert "flair" in form.errors

    def test_poll_option_lines_clean_to_list(self):
        community = make_community("poll-clean", allow_polls=True)
        form = PostCreateForm(
            data={"post_type": Post.PostType.POLL, "title": "Poll", "poll_option_lines": " Alpha \n\nBeta\n"},
            community=community,
        )

        assert form.is_valid() is True
        assert form.cleaned_data["poll_option_lines"] == ["Alpha", "Beta"]

    def test_clean_image_rejects_non_image_upload(self):
        community = make_community("bad-image")
        bad_file = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")
        form = PostCreateForm(
            data={"post_type": Post.PostType.IMAGE, "title": "Thread"},
            files={"image": bad_file},
            community=community,
        )

        assert form.is_valid() is False
        assert "image" in form.errors

    def test_flair_queryset_is_limited_to_community_flairs(self):
        community = make_community("flair-scope")
        other = make_community("flair-other")
        flair = PostFlair.objects.create(community=community, text="Local Flair")
        PostFlair.objects.create(community=other, text="Other Flair")
        form = PostCreateForm(community=community)

        assert list(form.fields["flair"].queryset) == [flair]
