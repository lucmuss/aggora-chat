import pytest
from django.contrib.auth import get_user_model

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
    def test_account_settings_accepts_profile_and_notification_values(self):
        user = make_user(username="settings", email="settings@example.com", handle="settings")
        form = AccountSettingsForm(
            data={
                "display_name": "Settings User",
                "bio": "Testing settings",
                "profile_visibility": User.ProfileVisibility.MEMBERS,
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
        assert saved.email_notifications_enabled is True
        assert saved.push_notifications_enabled is False
        assert saved.notify_on_replies is True
        assert saved.notify_on_follows is False

    def test_account_settings_bio_widget_enables_rich_markdown_preview(self):
        form = AccountSettingsForm()
        attrs = form.fields["bio"].widget.attrs

        assert attrs["data-rich-markdown"] == "true"
        assert attrs["data-markdown-preview-target"] == "account-bio-preview"


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
        attrs = form.fields["email"].widget.attrs

        assert attrs["placeholder"] == "you@example.com"
        assert attrs["autocomplete"] == "email"
        assert attrs["spellcheck"] == "false"

    def test_reset_password_key_form_sets_new_password_attributes(self):
        form = StyledResetPasswordKeyForm(user=None, temp_key="dummy")

        assert form.fields["password1"].widget.attrs["autocomplete"] == "new-password"
        assert form.fields["password2"].widget.attrs["autocomplete"] == "new-password"
