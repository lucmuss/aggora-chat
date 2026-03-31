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
