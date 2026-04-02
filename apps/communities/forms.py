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
            "sidebar_md": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "# Welcome to our community\n\nRules and guidelines go here...",
                    "data-markdown-preview-target": "community-sidebar-preview",
                    "data-markdown-preview-label": "Sidebar preview",
                }
            ),
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
            "landing_intro_md",
            "faq_md",
            "best_of_md",
            "seo_description",
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
            "sidebar_md": forms.Textarea(attrs={"rows": 6, "data-markdown-preview-target": "sidebar-settings-preview"}),
            "landing_intro_md": forms.Textarea(attrs={"rows": 5, "placeholder": "Why this community matters", "data-markdown-preview-target": "landing-intro-preview"}),
            "faq_md": forms.Textarea(attrs={"rows": 6, "placeholder": "## FAQ\n\n### What is this place?", "data-markdown-preview-target": "faq-preview"}),
            "best_of_md": forms.Textarea(attrs={"rows": 6, "placeholder": "- Best discussion\n- Community resources", "data-markdown-preview-target": "best-of-preview"}),
        }


class CommunityWikiPageForm(forms.ModelForm):
    class Meta:
        model = CommunityWikiPage
        fields = ["slug", "title", "body_md"]
        widgets = {
            "body_md": forms.Textarea(attrs={"rows": 14, "data-markdown-preview-target": "wiki-body-preview"}),
        }

    def clean_slug(self):
        return (self.cleaned_data.get("slug") or "").strip().lower()
