from django import forms

from apps.communities.models import Community

from .models import Post


class PostCreateForm(forms.ModelForm):
    poll_option_lines = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "One option per line"}),
        help_text="For poll posts, add one option per line.",
        label="Poll options",
    )

    class Meta:
        model = Post
        fields = [
            "post_type",
            "title",
            "body_md",
            "url",
            "image",
            "flair",
            "is_spoiler",
            "is_nsfw",
        ]
        widgets = {
            "body_md": forms.Textarea(
                attrs={
                    "rows": 8,
                    "data-markdown-preview-target": "post-markdown-preview",
                    "data-markdown-preview-label": "Post preview",
                }
            ),
        }

    def __init__(self, *args, community: Community, **kwargs):
        super().__init__(*args, **kwargs)
        self.community = community
        self.fields["flair"].queryset = community.post_flairs.all()

    def clean(self):
        cleaned_data = super().clean()
        post_type = cleaned_data.get("post_type")
        body_md = (cleaned_data.get("body_md") or "").strip()
        url = cleaned_data.get("url")
        image = cleaned_data.get("image")
        poll_option_lines = self.cleaned_data.get("poll_option_lines") or ""
        option_lines = [line.strip() for line in poll_option_lines.splitlines() if line.strip()]
        if post_type == Post.PostType.TEXT and not body_md:
            self.add_error("body_md", "Text posts need a body.")
        if post_type == Post.PostType.TEXT and not self.community.allow_text_posts:
            self.add_error("post_type", "Text posts are disabled in this community.")
        if post_type == Post.PostType.LINK and not url:
            self.add_error("url", "Link posts need a URL.")
        if post_type == Post.PostType.LINK and not self.community.allow_link_posts:
            self.add_error("post_type", "Link posts are disabled in this community.")
        if post_type == Post.PostType.IMAGE and not image:
            self.add_error("image", "Image posts need an image.")
        if post_type == Post.PostType.IMAGE and not self.community.allow_image_posts:
            self.add_error("post_type", "Image posts are disabled in this community.")
        if post_type == Post.PostType.POLL:
            if not self.community.allow_polls:
                self.add_error("post_type", "Polls are disabled in this community.")
            if len(option_lines) < 2:
                self.add_error("poll_option_lines", "Polls need at least two options.")
            if len(option_lines) > 6:
                self.add_error("poll_option_lines", "Polls support up to six options.")
        if self.community.require_post_flair and not cleaned_data.get("flair"):
            self.add_error("flair", "This community requires a post flair.")
        cleaned_data["poll_option_lines"] = option_lines
        return cleaned_data

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            return image
        content_type = getattr(image, "content_type", "")
        if content_type and not content_type.startswith("image/"):
            raise forms.ValidationError("Upload a valid image file.")
        return image
