import pytest
from django.contrib.auth import get_user_model

from apps.communities.forms import CommunityCreateForm, CommunitySettingsForm, CommunityWikiPageForm
from apps.communities.models import Community

User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "community_form_user"),
        "email": overrides.pop("email", "community_form_user@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", "community_form_user"),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug="forms", creator=None, **overrides):
    creator = creator or make_user(username=f"{slug}_creator", email=f"{slug}_creator@example.com", handle=f"{slug}_creator")
    data = {
        "name": slug.replace("-", " ").title(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "description": "Form tests",
        "creator": creator,
    }
    data.update(overrides)
    return Community.objects.create(**data)


@pytest.mark.django_db
class TestCommunityCreateForm:
    def test_clean_name_strips_whitespace(self):
        form = CommunityCreateForm(
            data={
                "name": "  Agora Builders  ",
                "slug": "agora-builders",
                "title": "Agora Builders",
                "description": "desc",
                "community_type": Community.CommunityType.PUBLIC,
            }
        )

        assert form.is_valid() is True
        assert form.cleaned_data["name"] == "Agora Builders"

    def test_clean_slug_normalizes_to_lowercase(self):
        form = CommunityCreateForm(
            data={
                "name": "Agora Builders",
                "slug": "Agora-Builders",
                "title": "Agora Builders",
                "description": "desc",
                "community_type": Community.CommunityType.PUBLIC,
            }
        )

        assert form.is_valid() is True
        assert form.cleaned_data["slug"] == "agora-builders"

    def test_duplicate_name_is_rejected_by_model_validation(self):
        make_community("existing", name="Existing Community", title="Existing Community")
        form = CommunityCreateForm(
            data={
                "name": "Existing Community",
                "slug": "new-slug",
                "title": "Another",
                "description": "desc",
                "community_type": Community.CommunityType.PUBLIC,
            }
        )

        assert form.is_valid() is False
        assert "name" in form.errors

    def test_duplicate_slug_is_rejected_by_model_validation(self):
        make_community("existing-slug")
        form = CommunityCreateForm(
            data={
                "name": "Another Community",
                "slug": "existing-slug",
                "title": "Another Community",
                "description": "desc",
                "community_type": Community.CommunityType.PUBLIC,
            }
        )

        assert form.is_valid() is False
        assert "slug" in form.errors


@pytest.mark.django_db
class TestCommunitySettingsForm:
    def test_accepts_privacy_and_post_rule_flags(self):
        community = make_community("settings-community")
        form = CommunitySettingsForm(
            data={
                "title": "Updated",
                "description": "Updated desc",
                "sidebar_md": "## Rules",
                "landing_intro_md": "Intro",
                "faq_md": "FAQ",
                "best_of_md": "Best of",
                "seo_description": "SEO copy",
                "community_type": Community.CommunityType.RESTRICTED,
                "allow_text_posts": "on",
                "allow_link_posts": "",
                "allow_image_posts": "on",
                "allow_polls": "on",
                "vote_hide_minutes": 90,
                "require_post_flair": "on",
            },
            instance=community,
        )

        assert form.is_valid() is True
        saved = form.save()
        assert saved.community_type == Community.CommunityType.RESTRICTED
        assert saved.allow_text_posts is True
        assert saved.allow_link_posts is False
        assert saved.allow_polls is True
        assert saved.require_post_flair is True

    def test_markdown_preview_widgets_are_present(self):
        form = CommunitySettingsForm()

        assert form.fields["sidebar_md"].widget.attrs["data-markdown-preview-target"] == "sidebar-settings-preview"
        assert form.fields["landing_intro_md"].widget.attrs["data-markdown-preview-target"] == "landing-intro-preview"
        assert form.fields["faq_md"].widget.attrs["data-markdown-preview-target"] == "faq-preview"
        assert form.fields["best_of_md"].widget.attrs["data-markdown-preview-target"] == "best-of-preview"


class TestCommunityWikiPageForm:
    def test_clean_slug_strips_and_lowercases(self):
        form = CommunityWikiPageForm(data={"slug": "  Home-Page  ", "title": "Home", "body_md": "Body"})

        assert form.is_valid() is True
        assert form.cleaned_data["slug"] == "home-page"

    def test_body_widget_has_markdown_preview_target(self):
        form = CommunityWikiPageForm()

        assert form.fields["body_md"].widget.attrs["data-markdown-preview-target"] == "wiki-body-preview"
