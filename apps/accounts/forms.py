from django import forms

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
