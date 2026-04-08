from __future__ import annotations

from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.common.image_variants import optimized_image_url
from apps.common.markdown import render_markdown
from apps.common.upload_paths import HashedUploadTo


class PostQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(is_removed=False, author_deleted_at__isnull=True)

    def visible_to(self, user):
        queryset = self.visible()
        if user is None or not getattr(user, "is_authenticated", False):
            return queryset.filter(is_nsfw=False)
        if not getattr(user, "allow_nsfw_content", False):
            return queryset.filter(is_nsfw=False)
        return queryset

    def for_listing(self):
        return self.select_related(
            "community",
            "author",
            "flair",
            "crosspost_parent",
            "crosspost_parent__community",
            "crosspost_parent__author",
        ).prefetch_related("poll__options", "poll__votes")


class Post(models.Model):
    class PostType(models.TextChoices):
        TEXT = "text", "Text"
        LINK = "link", "Link"
        IMAGE = "image", "Image"
        POLL = "poll", "Poll"
        CROSSPOST = "crosspost", "Crosspost"

    community = models.ForeignKey("communities.Community", on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, related_name="posts")
    post_type = models.CharField(max_length=12, choices=PostType.choices)
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=320, db_index=True)
    body_md = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    url = models.URLField(max_length=2000, blank=True)
    image = models.ImageField(upload_to=HashedUploadTo("original/post_images"), blank=True)
    flair = models.ForeignKey("communities.PostFlair", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    score = models.IntegerField(default=0, db_index=True)
    upvote_count = models.PositiveIntegerField(default=0)
    downvote_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    award_count = models.PositiveIntegerField(default=0)
    hot_score = models.FloatField(default=0.0, db_index=True)
    is_spoiler = models.BooleanField(default=False)
    is_nsfw = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    is_stickied = models.BooleanField(default=False)
    is_removed = models.BooleanField(default=False)
    removed_reason = models.TextField(blank=True)
    author_deleted_at = models.DateTimeField(null=True, blank=True)
    challenge = models.ForeignKey(
        "communities.CommunityChallenge",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="entries",
    )
    crosspost_parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-hot_score", "-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["-hot_score"]),
            models.Index(fields=["-score"]),
            models.Index(fields=["community", "-hot_score"]),
            models.Index(fields=["community", "-created_at"]),
            models.Index(fields=["author", "-created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:280] or "post"
            self.slug = f"{base_slug}-{timezone.now().strftime('%H%M%S')}"
        self.body_html = render_markdown(self.body_md)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title

    @property
    def image_original_url(self) -> str | None:
        return self.image.url if self.image else None

    @property
    def image_optimized_url(self) -> str | None:
        return optimized_image_url(self.image)

    @property
    def image_optimized_srcset(self) -> str:
        from apps.common.image_variants import optimized_image_srcset

        return optimized_image_srcset(self.image)


class Poll(models.Model):
    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name="poll")
    multiple_choice = models.BooleanField(default=False)
    closes_at = models.DateTimeField(null=True, blank=True)

    def is_open(self) -> bool:
        return self.closes_at is None or timezone.now() < self.closes_at


class PollOption(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=120)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class PollVote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(PollOption, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="poll_votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("poll", "user")


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True)
    body_md = models.TextField(max_length=10000)
    body_html = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    depth = models.PositiveSmallIntegerField(default=0)
    score = models.IntegerField(default=0, db_index=True)
    upvote_count = models.PositiveIntegerField(default=0)
    downvote_count = models.PositiveIntegerField(default=0)
    award_count = models.PositiveIntegerField(default=0)
    is_removed = models.BooleanField(default=False)
    is_collapsed = models.BooleanField(default=False)
    author_deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-score", "created_at"]
        indexes = [
            models.Index(fields=["post", "-score"]),
            models.Index(fields=["post", "created_at"]),
            models.Index(fields=["parent"]),
            models.Index(fields=["author", "-created_at"]),
        ]

    def save(self, *args, **kwargs):
        self.body_html = render_markdown(self.body_md)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Comment {self.pk} on {self.post_id}"
