from django import forms
from django.db import models

from apps.communities.models import Community

from .models import User


class HandleSetupForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["handle", "display_name"]
        widgets = {
            "handle": forms.TextInput(attrs={"placeholder": "your_handle"}),
            "display_name": forms.TextInput(attrs={"placeholder": "Display name"}),
        }

    def clean_handle(self) -> str:
        handle = (self.cleaned_data.get("handle") or "").strip().lower()
        if User.objects.filter(handle=handle).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This handle is already taken.")
        return handle


class SignupForm(forms.Form):
    first_name = forms.CharField(max_length=30, label="First name", required=False)
    last_name = forms.CharField(max_length=30, label="Last name", required=False)

    def signup(self, request, user):
        user.first_name = self.cleaned_data.get("first_name") or ""
        user.last_name = self.cleaned_data.get("last_name") or ""
        user.save()


class AccountSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "display_name",
            "bio",
            "avatar",
            "profile_visibility",
            "email_notifications_enabled",
            "push_notifications_enabled",
            "notify_on_replies",
            "notify_on_follows",
            "notify_on_challenges",
        ]
        widgets = {
            "bio": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Tell your communities what you care about.",
                    "data-rich-markdown": "true",
                    "data-markdown-preview-target": "account-bio-preview",
                    "data-markdown-preview-label": "Bio preview",
                }
            ),
        }


class TotpVerificationForm(forms.Form):
    code = forms.CharField(
        max_length=12,
        label="Authenticator code",
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "placeholder": "123456",
            }
        ),
        help_text="Enter the current 6-digit code from your authenticator app.",
    )


class StartWithFriendsForm(forms.Form):
    class FirstContributionType(models.TextChoices):
        POST = "post", "Write a first post"
        COMMENT = "comment", "Reply to a thread"

    display_name = forms.CharField(
        required=False,
        max_length=50,
        label="Display name",
        widget=forms.TextInput(
            attrs={
                "placeholder": "How should people see you?",
            }
        ),
    )
    bio = forms.CharField(
        required=False,
        label="Short bio",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "A sentence or two about what you care about.",
                "data-rich-markdown": "true",
                "data-markdown-preview-target": "onboarding-bio-preview",
                "data-markdown-preview-label": "Bio preview",
            }
        ),
    )
    communities = forms.ModelMultipleChoiceField(
        queryset=Community.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Suggested communities",
    )
    friend_emails = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "friend1@example.com\nfriend2@example.com",
            }
        ),
        label="Invite friends",
        help_text="Add one email per line. We'll send a join link for your chosen community.",
    )
    first_post_community = forms.ModelChoiceField(
        queryset=Community.objects.none(),
        required=False,
        empty_label="Pick later",
        label="Create your first post in",
    )
    first_contribution_type = forms.ChoiceField(
        choices=FirstContributionType.choices,
        initial=FirstContributionType.POST,
        widget=forms.RadioSelect,
        label="First contribution",
        help_text="Choose whether we should drop you into the composer or a reply-friendly thread.",
    )

    def __init__(self, *args, suggested_communities=None, joined_communities=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        suggested_list = list(suggested_communities or [])
        joined_list = list(joined_communities or [])
        suggested_ids = [community.pk for community in suggested_list]
        joined_ids = [community.pk for community in joined_list]
        self.fields["communities"].queryset = Community.objects.filter(pk__in=suggested_ids)
        self.fields["first_post_community"].queryset = Community.objects.filter(pk__in=joined_ids)
        self.fields["communities"].initial = suggested_ids[:3]
        first_choice = joined_list[0] if joined_list else None
        if first_choice:
            self.fields["first_post_community"].initial = first_choice.pk
        if self.user is not None and getattr(self.user, "pk", None):
            self.fields["display_name"].initial = self.user.display_name
            self.fields["bio"].initial = self.user.bio

    def clean_friend_emails(self):
        raw_value = (self.cleaned_data.get("friend_emails") or "").strip()
        if not raw_value:
            return []
        emails = []
        for line in raw_value.replace(",", "\n").splitlines():
            email = line.strip().lower()
            if not email:
                continue
            validator = forms.EmailField()
            validator.clean(email)
            emails.append(email)
        return list(dict.fromkeys(emails))
