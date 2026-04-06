from django import forms

from apps.communities.models import Community

from .models import Post


class PostCreateForm(forms.ModelForm):
    is_safe_for_work = forms.BooleanField(
        required=False,
        initial=True,
        label="This post is safe for work",
        help_text="Leave this on for normal posts. Turn it off only when the thread contains 18+ sexual content or media.",
    )
    poll_option_lines = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "One option per line"}),
        help_text="For poll posts, add one option per line.",
        label="Poll options",
    )
    challenge = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="No challenge entry",
        label="Challenge entry",
        help_text="Attach this post to the current featured challenge when it fits.",
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
            "challenge",
            "is_spoiler",
        ]
        widgets = {
            "body_md": forms.Textarea(
                attrs={
                    "rows": 8,
                    "data-rich-markdown": "true",
                    "data-markdown-preview-target": "post-markdown-preview",
                    "data-markdown-preview-label": "Post preview",
                    "data-mentions-url": "/accounts/mentions/search/",
                }
            ),
        }

    def __init__(self, *args, community: Community, **kwargs):
        super().__init__(*args, **kwargs)
        self.community = community
        self.order_fields(
            [
                "post_type",
                "title",
                "body_md",
                "url",
                "image",
                "flair",
                "challenge",
                "is_spoiler",
                "is_safe_for_work",
                "poll_option_lines",
            ]
        )
        if self.instance and getattr(self.instance, "pk", None):
            self.fields["is_safe_for_work"].initial = not self.instance.is_nsfw
        self.fields["flair"].queryset = community.post_flairs.all()
        self.fields["body_md"].widget.attrs["data-community-slug"] = community.slug
        active_challenges = [
            challenge
            for challenge in community.challenges.filter(is_featured=True).order_by("-starts_at")
            if challenge.is_active()
        ]
        active_challenge_ids = [challenge.id for challenge in active_challenges]
        self.fields["challenge"].queryset = community.challenges.filter(id__in=active_challenge_ids)
        if active_challenges:
            self.fields["challenge"].initial = active_challenges[0]

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
        challenge = cleaned_data.get("challenge")
        if challenge and challenge.community_id != self.community.id:
            self.add_error("challenge", "Choose a challenge from this community.")
        if challenge and not challenge.is_active():
            self.add_error("challenge", "This challenge is no longer active.")
        safe_for_work = cleaned_data.get("is_safe_for_work", True)
        if self.is_bound and "is_safe_for_work" not in self.data:
            safe_for_work = True
        cleaned_data["is_nsfw"] = not bool(safe_for_work)
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
