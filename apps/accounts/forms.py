from datetime import date

from django import forms
from django.db import models
from PIL import Image

from apps.communities.models import Community

from .countries import COUNTRY_NAME_SET, COUNTRY_NAMES, COUNTRY_SEARCH_INDEX, canonicalize_country_name
from .models import User
from .regions import COUNTRY_CODE_BY_NAME, REGIONS_BY_COUNTRY


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
    region = forms.ChoiceField(
        required=False,
        choices=[("", "Select region")],
    )
    city = forms.CharField(
        required=False,
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "type": "search",
                "list": "city-suggestions",
                "placeholder": "Start typing your city",
                "autocomplete": "address-level2",
                "spellcheck": "false",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["handle"].required = True
        country = ""
        if self.is_bound:
            country = canonicalize_country_name((self.data.get("country") or "").strip())
        elif self.instance and self.instance.pk:
            country = (self.instance.country or "").strip()
        self.fields["region"].choices = [("", "Select region")] + [
            (region_name, region_name) for region_name in REGIONS_BY_COUNTRY.get(country, [])
        ]

    class Meta:
        model = User
        fields = [
            "handle",
            "display_name",
            "bio",
            "avatar",
            "banner",
            "birth_date",
            "country",
            "region",
            "city",
            "profile_visibility",
            "preferred_theme",
            "preferred_language",
            "allow_nsfw_content",
            "email_notifications_enabled",
            "push_notifications_enabled",
            "notify_on_replies",
            "notify_on_follows",
            "notify_on_challenges",
        ]
        widgets = {
            "handle": forms.TextInput(
                attrs={
                    "placeholder": "your_handle",
                    "autocapitalize": "none",
                    "spellcheck": "false",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "you@example.com",
                    "autocomplete": "email",
                    "spellcheck": "false",
                }
            ),
            "bio": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Tell your communities what you care about.",
                    "data-rich-markdown": "true",
                    "data-markdown-preview-target": "account-bio-preview",
                    "data-markdown-preview-label": "Bio preview",
                }
            ),
            "birth_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "max": date.today().isoformat(),
                    "class": "w-full min-h-[42px] rounded-g border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 shadow-none",
                }
            ),
            "country": forms.TextInput(
                attrs={
                    "list": "country-options",
                    "placeholder": "Start typing your country",
                    "autocomplete": "country-name",
                    "spellcheck": "false",
                }
            ),
            "region": forms.Select(
                attrs={
                    "data-location-region": "true",
                }
            ),
        }
        help_texts = {
            "handle": "This is your public @name. Use lowercase letters, numbers, and underscores.",
            "birth_date": "Used to show your age on your public profile.",
            "country": "Choose the country you want to show on your profile.",
            "region": "Agora will narrow this list to the regions that belong to your selected country.",
            "city": "Type your city. If Google Places is enabled, suggestions will appear automatically.",
            "preferred_theme": "Pick which color theme Agora should use by default on your devices.",
            "preferred_language": "Choose the interface language Agora should use after you save these settings.",
            "allow_nsfw_content": "Turn this on if you want 18+ posts and media to appear in feeds and thread lists.",
        }

    def clean_handle(self) -> str:
        handle = (self.cleaned_data.get("handle") or "").strip().lower()
        if User.objects.filter(handle=handle).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This handle is already taken.")
        return handle

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get("birth_date")
        if birth_date and birth_date > date.today():
            raise forms.ValidationError("Birth date can't be in the future.")
        return birth_date

    def clean_country(self) -> str:
        country = canonicalize_country_name((self.cleaned_data.get("country") or "").strip())
        if country and country.casefold() not in COUNTRY_NAME_SET:
            raise forms.ValidationError("Choose a country from the list so your profile stays consistent.")
        return country

    def clean_region(self) -> str:
        region = (self.cleaned_data.get("region") or "").strip()
        country = (self.cleaned_data.get("country") or "").strip()
        valid_regions = REGIONS_BY_COUNTRY.get(country, [])
        if region and not country:
            raise forms.ValidationError("Choose your country before selecting a region.")
        if region and valid_regions and region not in valid_regions:
            raise forms.ValidationError("Choose a region that belongs to the selected country.")
        return region

    def clean_city(self) -> str:
        return (self.cleaned_data.get("city") or "").strip()

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if not avatar:
            return avatar
        content_type = getattr(avatar, "content_type", "")
        if content_type and not content_type.startswith("image/"):
            raise forms.ValidationError("Upload a valid image file for your avatar.")
        if getattr(avatar, "size", 0) > 2 * 1024 * 1024:
            raise forms.ValidationError("Avatar images must be 2 MB or smaller.")
        return avatar

    def clean_banner(self):
        banner = self.cleaned_data.get("banner")
        if not banner:
            return banner
        content_type = getattr(banner, "content_type", "")
        if content_type and not content_type.startswith("image/"):
            raise forms.ValidationError("Upload a valid image file for your profile banner.")
        if getattr(banner, "size", 0) > 4 * 1024 * 1024:
            raise forms.ValidationError("Banner images must be 4 MB or smaller.")
        try:
            image = Image.open(banner)
            width, height = image.size
            if not width or not height:
                raise forms.ValidationError("Banner image dimensions could not be read.")
            ratio = width / height
            if ratio < 2.0 or ratio > 6.0:
                raise forms.ValidationError("Banner images should be wide, roughly between 2:1 and 6:1.")
        finally:
            if hasattr(banner, "seek"):
                banner.seek(0)
        return banner

    @property
    def country_names(self):
        return COUNTRY_NAMES

    @property
    def regions_by_country(self):
        return REGIONS_BY_COUNTRY

    @property
    def country_code_by_name(self):
        return COUNTRY_CODE_BY_NAME

    @property
    def country_search_index(self):
        return COUNTRY_SEARCH_INDEX


class TotpVerificationForm(forms.Form):
    code = forms.CharField(
        max_length=12,
        label="Authenticator code",
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "spellcheck": "false",
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
