from django import forms

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


class StartWithFriendsForm(forms.Form):
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

    def __init__(self, *args, suggested_communities=None, joined_communities=None, **kwargs):
        super().__init__(*args, **kwargs)
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
