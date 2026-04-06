from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Q

from allauth.account.forms import ResetPasswordForm, ResetPasswordKeyForm
from allauth.account.internal import flows
from allauth.account.utils import filter_users_by_email, user_email

User = get_user_model()


class StyledResetPasswordForm(ResetPasswordForm):
    identifier = forms.CharField(required=True, label="Email address or username")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("email", None)
        self.fields["identifier"].widget.attrs.update(
            {
                "placeholder": "you@example.com or your username",
                "autocomplete": "username",
                "spellcheck": "false",
            }
        )
        self.user_lookup = []

    def clean_identifier(self) -> str:
        identifier = (self.cleaned_data.get("identifier") or "").strip()
        lookup_value = identifier.lower()
        users = list(filter_users_by_email(lookup_value, is_active=True, prefer_verified=True))
        if not users:
            users = list(
                User.objects.filter(
                    is_active=True,
                ).filter(
                    Q(username__iexact=lookup_value) | Q(handle__iexact=lookup_value)
                )
            )
        deduped = []
        seen_ids = set()
        for user in users:
            if user.pk in seen_ids:
                continue
            deduped.append(user)
            seen_ids.add(user.pk)
        self.user_lookup = deduped
        if not self.user_lookup:
            raise forms.ValidationError("We couldn't find an account for that email address or username.")
        return identifier

    def clean(self):
        cleaned_data = super().clean()
        if self.user_lookup:
            cleaned_data["email"] = user_email(self.user_lookup[0]) or ""
        return cleaned_data

    def save(self, request, **kwargs) -> str:
        token_generator = kwargs.get("token_generator", default_token_generator)
        email = self.cleaned_data.get("email") or self.cleaned_data["identifier"]
        flows.password_reset.request_password_reset(
            request,
            email,
            self.user_lookup,
            token_generator,
        )
        return email


class StyledResetPasswordKeyForm(ResetPasswordKeyForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, placeholder in {
            "password1": "New password",
            "password2": "Repeat new password",
        }.items():
            self.fields[field_name].widget.attrs.update(
                {
                    "placeholder": placeholder,
                    "autocomplete": "new-password",
                }
            )
