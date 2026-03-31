from django import forms

from .models import Community, CommunityWikiPage


class CommunityCreateForm(forms.ModelForm):
    class Meta:
        model = Community
        fields = [
            "name",
            "slug",
            "title",
            "description",
            "sidebar_md",
            "icon",
            "banner",
            "community_type",
        ]
        labels = {
            "name": "Community name",
            "slug": "Slug",
            "title": "Display title",
            "description": "Short description",
            "sidebar_md": "Sidebar content (Markdown)",
            "community_type": "Privacy type",
        }
        help_texts = {
            "name": "The full display name for your community.",
            "slug": "The unique URL identifier for your community (e.g. 'coding' for c/coding).",
            "title": "A catchy title that appears at the top of the community page.",
            "sidebar_md": "Information about the community that appears in the right sidebar. Supports Markdown.",
            "community_type": "Control who can view and join this community.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "What is this community about?"}),
            "sidebar_md": forms.Textarea(attrs={"rows": 6, "placeholder": "# Welcome to our community\n\nRules and guidelines go here..."}),
        }

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()

    def clean_slug(self):
        return (self.cleaned_data.get("slug") or "").strip().lower()


class CommunitySettingsForm(forms.ModelForm):
    class Meta:
        model = Community
        fields = [
            "title",
            "description",
            "sidebar_md",
            "community_type",
            "allow_text_posts",
            "allow_link_posts",
            "allow_image_posts",
            "allow_polls",
            "vote_hide_minutes",
            "require_post_flair",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "sidebar_md": forms.Textarea(attrs={"rows": 6}),
        }


class CommunityWikiPageForm(forms.ModelForm):
    class Meta:
        model = CommunityWikiPage
        fields = ["slug", "title", "body_md"]
        widgets = {
            "body_md": forms.Textarea(attrs={"rows": 14}),
        }

    def clean_slug(self):
        return (self.cleaned_data.get("slug") or "").strip().lower()
