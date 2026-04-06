from django import forms

from apps.common.markdown import render_markdown

from .models import ModMail, ModMailMessage, RemovalReason


class ContentReportForm(forms.Form):
    REASON_SPAM = "spam"
    REASON_HARASSMENT = "harassment"
    REASON_HATE = "hate"
    REASON_ADULT = "adult"
    REASON_MISINFORMATION = "misinformation"
    REASON_OTHER = "other"
    REASON_CHOICES = (
        (REASON_SPAM, "Spam or scam"),
        (REASON_HARASSMENT, "Harassment or bullying"),
        (REASON_HATE, "Hate or abusive content"),
        (REASON_ADULT, "Sexual or graphic content"),
        (REASON_MISINFORMATION, "Misleading or harmful claims"),
        (REASON_OTHER, "Something else"),
    )

    reason = forms.ChoiceField(choices=REASON_CHOICES)
    details = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Add context for the moderators (optional).",
            }
        ),
    )


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
