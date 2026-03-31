from django.db import models
from django.utils.text import slugify

from apps.common.markdown import render_markdown


class Community(models.Model):
    class CommunityType(models.TextChoices):
        PUBLIC = "public", "Public"
        RESTRICTED = "restricted", "Restricted"
        PRIVATE = "private", "Private"

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, db_index=True)
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=5000, blank=True)
    sidebar_md = models.TextField(blank=True)
    sidebar_html = models.TextField(blank=True)
    icon = models.ImageField(upload_to="community_icons/", blank=True)
    banner = models.ImageField(upload_to="community_banners/", blank=True)
    community_type = models.CharField(
        max_length=12,
        choices=CommunityType.choices,
        default=CommunityType.PUBLIC,
    )
    creator = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_communities",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    subscriber_count = models.PositiveIntegerField(default=0)
    allow_text_posts = models.BooleanField(default=True)
    allow_link_posts = models.BooleanField(default=True)
    allow_image_posts = models.BooleanField(default=True)
    allow_polls = models.BooleanField(default=False)
    vote_hide_minutes = models.PositiveIntegerField(default=60)
    require_post_flair = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "communities"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        self.sidebar_html = render_markdown(self.sidebar_md)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"c/{self.slug}"


class CommunityMembership(models.Model):
    class Role(models.TextChoices):
        MEMBER = "member", "Member"
        MODERATOR = "moderator", "Moderator"
        OWNER = "owner", "Owner"
        AGENT_MOD = "agent_mod", "Agent Moderator"

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "community")
        indexes = [
            models.Index(fields=["community", "role"]),
            models.Index(fields=["user", "community"]),
        ]


class CommunityRule(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="rules",
    )
    order = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=1000, blank=True)

    class Meta:
        ordering = ["order", "id"]


class PostFlair(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="post_flairs",
    )
    text = models.CharField(max_length=64)
    css_class = models.CharField(max_length=30, blank=True)
    bg_color = models.CharField(max_length=7, default="#6B7280")


class UserFlair(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    text = models.CharField(max_length=64)
    css_class = models.CharField(max_length=30, blank=True)

    class Meta:
        unique_together = ("community", "user")


class CommunityWikiPage(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="wiki_pages",
    )
    slug = models.SlugField(max_length=80)
    title = models.CharField(max_length=120)
    body_md = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_wiki_pages",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("community", "slug")
        ordering = ["slug"]

    def save(self, *args, **kwargs):
        self.body_html = render_markdown(self.body_md)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.community.slug}:{self.slug}"
