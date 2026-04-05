from django import forms

from apps.common.markdown import render_markdown

from .models import ModMail, ModMailMessage, RemovalReason


class RemovalReasonForm(forms.ModelForm):
    class Meta:
        model = RemovalReason
        fields = ["code", "title", "message_md", "order"]
        widgets = {
            "message_md": forms.Textarea(attrs={"rows": 4, "data-rich-markdown": "true"}),
        }


class ModMailCreateForm(forms.ModelForm):
    body_md = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "data-rich-markdown": "true",
                "data-markdown-preview-target": "modmail-create-preview",
            }
        )
    )

    class Meta:
        model = ModMail
        fields = ["subject"]


class ModMailReplyForm(forms.ModelForm):
    class Meta:
        model = ModMailMessage
        fields = ["body_md"]
        widgets = {
            "body_md": forms.Textarea(
                attrs={
                    "rows": 4,
                    "data-rich-markdown": "true",
                    "data-markdown-preview-target": "modmail-reply-preview",
                }
            ),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.body_html = render_markdown(instance.body_md)
        if commit:
            instance.save()
        return instance
