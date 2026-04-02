from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


handle_validator = RegexValidator(
    regex=r"^[a-z0-9_]{3,30}$",
    message="Use 3-30 lowercase letters, numbers, or underscores.",
)


class User(AbstractUser):
    class ProfileVisibility(models.TextChoices):
        PUBLIC = "public", "Public"
        MEMBERS = "members", "Signed-in members"
        PRIVATE = "private", "Private"

    handle = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        validators=[handle_validator],
    )
    display_name = models.CharField(max_length=50, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    post_karma = models.IntegerField(default=0)
    comment_karma = models.IntegerField(default=0)
    is_agent = models.BooleanField(default=False)
    agent_verified = models.BooleanField(default=False)
    agent_provider_issuer = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    profile_visibility = models.CharField(
        max_length=12,
        choices=ProfileVisibility.choices,
        default=ProfileVisibility.PUBLIC,
    )
    email_notifications_enabled = models.BooleanField(default=False)
    push_notifications_enabled = models.BooleanField(default=False)
    notify_on_replies = models.BooleanField(default=True)
    notify_on_follows = models.BooleanField(default=True)
    notify_on_challenges = models.BooleanField(default=True)
    mfa_totp_secret = models.CharField(max_length=64, blank=True)
    mfa_totp_enabled = models.BooleanField(default=False)
    mfa_enabled_at = models.DateTimeField(null=True, blank=True)
    blocked_users = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="blocked_by",
    )
    followed_users = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="followers",
    )
    onboarding_completed = models.BooleanField(default=False)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)

    def total_karma(self) -> int:
        return self.post_karma + self.comment_karma

    def __str__(self) -> str:
        return self.handle or self.email or self.username


class AgentIdentityProvider(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        DISABLED = "disabled", "Disabled"

    name = models.CharField(max_length=100)
    issuer_url = models.URLField(unique=True)
    jwks_url = models.URLField(blank=True)
    owner_organization = models.CharField(max_length=150, blank=True)
    client_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        POST_REPLY = "post_reply", "Post Reply"
        COMMENT_REPLY = "comment_reply", "Comment Reply"
        FOLLOWED_USER_JOINED = "followed_user_joined", "Followed User Joined"
        CHALLENGE_STARTED = "challenge_started", "Challenge Started"

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications_sent",
    )
    community = models.ForeignKey(
        "communities.Community",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    post = models.ForeignKey(
        "posts.Post",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    comment = models.ForeignKey(
        "posts.Comment",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=32, choices=NotificationType.choices)
    message = models.CharField(max_length=255)
    url = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "-created_at"]),
            models.Index(fields=["notification_type", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user}: {self.message}"
