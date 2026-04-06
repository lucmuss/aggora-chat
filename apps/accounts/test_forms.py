import pytest
from io import BytesIO
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import RequestFactory, override_settings
from PIL import Image

from apps.accounts.allauth_forms import StyledResetPasswordForm, StyledResetPasswordKeyForm
from apps.accounts.forms import (
    AccountSettingsForm,
    HandleSetupForm,
    SignupForm,
    StartWithFriendsForm,
    TotpVerificationForm,
)
from apps.communities.models import Community

User = get_user_model()


def make_user(**overrides):
    data = {
        "username": overrides.pop("username", "user_form"),
        "email": overrides.pop("email", "user_form@example.com"),
        "password": overrides.pop("password", "password123"),
        "handle": overrides.pop("handle", None),
    }
    data.update(overrides)
    return User.objects.create_user(**data)


def make_community(slug, creator):
    return Community.objects.create(
        name=slug.replace("-", " ").title(),
        slug=slug,
        title=slug.replace("-", " ").title(),
        description="Community for form tests",
        creator=creator,
    )


@pytest.mark.django_db
class TestHandleSetupForm:
    def test_clean_handle_lowercases_valid_value(self):
        user = make_user(username="handle_owner", email="handle_owner@example.com")
        form = HandleSetupForm(data={"handle": "Agora_User", "display_name": "Agora User"}, instance=user)

        assert form.is_valid() is True
        assert form.cleaned_data["handle"] == "agora_user"

    def test_clean_handle_rejects_duplicate(self):
        make_user(username="taken", email="taken@example.com", handle="taken_handle")
        user = make_user(username="new", email="new@example.com")
        form = HandleSetupForm(data={"handle": "taken_handle", "display_name": "New User"}, instance=user)

        assert form.is_valid() is False
        assert "handle" in form.errors


@pytest.mark.django_db
class TestSignupForm:
    def test_signup_persists_first_and_last_name(self):
        user = make_user(username="signup", email="signup@example.com")
        form = SignupForm(data={"first_name": "Ada", "last_name": "Lovelace"})

        assert form.is_valid() is True
        form.signup(None, user)
        user.refresh_from_db()

        assert user.first_name == "Ada"
        assert user.last_name == "Lovelace"


@pytest.mark.django_db
class TestAccountSettingsForm:
    @staticmethod
    def _banner_file(width=1600, height=400):
        file_obj = BytesIO()
        Image.new("RGB", (width, height), color="#0d9488").save(file_obj, format="PNG")
        file_obj.seek(0)
        return SimpleUploadedFile("banner.png", file_obj.read(), content_type="image/png")

    def test_account_settings_accepts_profile_and_notification_values(self):
        user = make_user(username="settings", email="settings@example.com", handle="settings")
        form = AccountSettingsForm(
            data={
                "handle": "settings",
                "display_name": "Settings User",
                "bio": "Testing settings",
                "birth_date": "1994-04-15",
                "country": "Germany",
                "region": "Berlin",
                "city": "Berlin",
                "profile_visibility": User.ProfileVisibility.MEMBERS,
                "preferred_theme": User.PreferredTheme.DARK,
                "preferred_language": User.PreferredLanguage.ENGLISH,
                "allow_nsfw_content": "on",
                "email_notifications_enabled": "on",
                "push_notifications_enabled": "",
                "notify_on_replies": "on",
                "notify_on_follows": "",
                "notify_on_challenges": "on",
            },
            instance=user,
        )

        assert form.is_valid() is True
        saved = form.save()

        assert saved.profile_visibility == User.ProfileVisibility.MEMBERS
        assert saved.country == "Germany"
        assert saved.region == "Berlin"
        assert saved.city == "Berlin"
        assert saved.preferred_theme == User.PreferredTheme.DARK
        assert saved.preferred_language == User.PreferredLanguage.ENGLISH
        assert saved.allow_nsfw_content is True
        assert saved.email_notifications_enabled is True
        assert saved.push_notifications_enabled is False
        assert saved.notify_on_replies is True
        assert saved.notify_on_follows is False

    def test_account_settings_bio_widget_enables_rich_markdown_preview(self):
        form = AccountSettingsForm()
        attrs = form.fields["bio"].widget.attrs

        assert attrs["data-rich-markdown"] == "true"
        assert attrs["data-markdown-preview-target"] == "account-bio-preview"

    def test_account_settings_uses_account_email_management_view_instead_of_inline_email_field(self):
        form = AccountSettingsForm()

        assert "email" not in form.fields

    def test_account_settings_rejects_avatar_larger_than_two_mb(self):
        oversized = SimpleUploadedFile("avatar.png", b"x" * (2 * 1024 * 1024 + 1), content_type="image/png")
        user = make_user(username="avatar", email="avatar@example.com", handle="avatar")
        form = AccountSettingsForm(
            data={
                "handle": "avatar",
                "display_name": "Avatar User",
                "bio": "",
                "birth_date": "",
                "country": "",
                "profile_visibility": User.ProfileVisibility.PUBLIC,
                "preferred_theme": User.PreferredTheme.LIGHT,
                "preferred_language": User.PreferredLanguage.ENGLISH,
                "email_notifications_enabled": "",
                "push_notifications_enabled": "",
                "notify_on_replies": "",
                "notify_on_follows": "",
                "notify_on_challenges": "",
            },
            files={"avatar": oversized},
            instance=user,
        )

        assert form.is_valid() is False
        assert "avatar" in form.errors

    def test_account_settings_rejects_unknown_country(self):
        user = make_user(username="country", email="country@example.com", handle="country")
        form = AccountSettingsForm(
            data={
                "handle": "country",
                "display_name": "Country User",
                "bio": "",
                "birth_date": "",
                "country": "Atlantis",
                "profile_visibility": User.ProfileVisibility.PUBLIC,
                "preferred_theme": User.PreferredTheme.LIGHT,
                "preferred_language": User.PreferredLanguage.ENGLISH,
                "email_notifications_enabled": "",
                "push_notifications_enabled": "",
                "notify_on_replies": "",
                "notify_on_follows": "",
                "notify_on_challenges": "",
            },
            instance=user,
        )

        assert form.is_valid() is False
        assert "country" in form.errors

    def test_account_settings_rejects_region_that_does_not_match_country(self):
        user = make_user(username="regionbad", email="regionbad@example.com", handle="regionbad")
        form = AccountSettingsForm(
            data={
                "handle": "regionbad",
                "display_name": "Region User",
                "bio": "",
                "birth_date": "",
                "country": "Germany",
                "region": "California",
                "city": "Berlin",
                "profile_visibility": User.ProfileVisibility.PUBLIC,
                "preferred_theme": User.PreferredTheme.LIGHT,
                "preferred_language": User.PreferredLanguage.ENGLISH,
                "email_notifications_enabled": "",
                "push_notifications_enabled": "",
                "notify_on_replies": "",
                "notify_on_follows": "",
                "notify_on_challenges": "",
            },
            instance=user,
        )

        assert form.is_valid() is False
        assert "region" in form.errors

    def test_account_settings_accepts_wide_banner_image(self):
        user = make_user(username="bannerok", email="bannerok@example.com", handle="bannerok")
        form = AccountSettingsForm(
            data={
                "handle": "bannerok",
                "display_name": "Banner User",
                "bio": "",
                "birth_date": "",
                "country": "",
                "profile_visibility": User.ProfileVisibility.PUBLIC,
                "preferred_theme": User.PreferredTheme.LIGHT,
                "preferred_language": User.PreferredLanguage.ENGLISH,
                "email_notifications_enabled": "",
                "push_notifications_enabled": "",
                "allow_nsfw_content": "",
                "notify_on_replies": "",
                "notify_on_follows": "",
                "notify_on_challenges": "",
            },
            files={"banner": self._banner_file()},
            instance=user,
        )

        assert form.is_valid() is True

    def test_account_settings_rejects_tall_banner_image(self):
        user = make_user(username="bannerbad", email="bannerbad@example.com", handle="bannerbad")
        form = AccountSettingsForm(
            data={
                "handle": "bannerbad",
                "display_name": "Banner User",
                "bio": "",
                "birth_date": "",
                "country": "",
                "profile_visibility": User.ProfileVisibility.PUBLIC,
                "preferred_theme": User.PreferredTheme.LIGHT,
                "preferred_language": User.PreferredLanguage.ENGLISH,
                "email_notifications_enabled": "",
                "push_notifications_enabled": "",
                "allow_nsfw_content": "",
                "notify_on_replies": "",
                "notify_on_follows": "",
                "notify_on_challenges": "",
            },
            files={"banner": self._banner_file(width=800, height=700)},
            instance=user,
        )

        assert form.is_valid() is False
        assert "banner" in form.errors


class TestTotpVerificationForm:
    def test_totp_verification_form_accepts_code_field(self):
        form = TotpVerificationForm(data={"code": "123456"})

        assert form.is_valid() is True

    def test_totp_verification_widget_has_numeric_autocomplete(self):
        form = TotpVerificationForm()
        attrs = form.fields["code"].widget.attrs

        assert attrs["inputmode"] == "numeric"
        assert attrs["autocomplete"] == "one-time-code"
        assert attrs["spellcheck"] == "false"
        assert "placeholder" not in attrs


@pytest.mark.django_db
class TestStartWithFriendsForm:
    def test_init_limits_querysets_and_prefills_profile_fields(self):
        user = make_user(username="starter", email="starter@example.com", handle="starter", display_name="Starter", bio="Bio")
        communities = [make_community(f"community-{index}", user) for index in range(4)]
        form = StartWithFriendsForm(
            suggested_communities=communities,
            joined_communities=communities[:2],
            user=user,
        )

        assert list(form.fields["communities"].queryset.values_list("pk", flat=True)) == [community.pk for community in communities]
        assert list(form.fields["first_post_community"].queryset.values_list("pk", flat=True)) == [community.pk for community in communities[:2]]
        assert form.fields["display_name"].initial == "Starter"
        assert form.fields["bio"].initial == "Bio"
        assert form.fields["first_post_community"].initial == communities[0].pk
        assert form.fields["bio"].widget.attrs["data-rich-markdown"] == "true"
        assert form.fields["bio"].widget.attrs["data-markdown-preview-target"] == "onboarding-bio-preview"

    def test_clean_friend_emails_deduplicates_and_normalizes(self):
        user = make_user(username="emails", email="emails@example.com", handle="emails")
        community = make_community("email-community", user)
        form = StartWithFriendsForm(
            data={
                "friend_emails": "Friend@example.com\nfriend@example.com,second@example.com\n",
                "first_contribution_type": StartWithFriendsForm.FirstContributionType.POST,
            },
            suggested_communities=[community],
            joined_communities=[community],
            user=user,
        )

        assert form.is_valid() is True
        assert form.cleaned_data["friend_emails"] == ["friend@example.com", "second@example.com"]

    def test_clean_friend_emails_rejects_invalid_addresses(self):
        user = make_user(username="broken", email="broken@example.com", handle="broken")
        community = make_community("broken-community", user)
        form = StartWithFriendsForm(
            data={
                "friend_emails": "not-an-email",
                "first_contribution_type": StartWithFriendsForm.FirstContributionType.POST,
            },
            suggested_communities=[community],
            joined_communities=[community],
            user=user,
        )

        assert form.is_valid() is False
        assert "friend_emails" in form.errors


class TestStyledAllauthForms:
    def test_reset_password_form_sets_widget_attributes(self):
        form = StyledResetPasswordForm()
        attrs = form.fields["identifier"].widget.attrs

        assert attrs["placeholder"] == "you@example.com or your username"
        assert attrs["autocomplete"] == "username"
        assert attrs["spellcheck"] == "false"

    @pytest.mark.django_db
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reset_password_form_accepts_username_and_sends_email(self):
        user = make_user(username="resetuser", email="resetuser@example.com", handle="resetuser")
        form = StyledResetPasswordForm(data={"identifier": "resetuser"})

        assert form.is_valid() is True
        email = form.save(RequestFactory().post("/accounts/password/reset/"))

        assert email == user.email
        assert len(mail.outbox) == 1
        assert user.email in mail.outbox[0].to

    @pytest.mark.django_db
    def test_reset_password_form_rejects_unknown_identifier(self):
        form = StyledResetPasswordForm(data={"identifier": "missing-user"})

        assert form.is_valid() is False
        assert "identifier" in form.errors

    def test_reset_password_key_form_sets_new_password_attributes(self):
        form = StyledResetPasswordKeyForm(user=None, temp_key="dummy")

        assert form.fields["password1"].widget.attrs["autocomplete"] == "new-password"
        assert form.fields["password2"].widget.attrs["autocomplete"] == "new-password"
