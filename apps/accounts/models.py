from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


handle_validator = RegexValidator(
    regex=r"^[a-z0-9_]{3,30}$",
    message="Use 3-30 lowercase letters, numbers, or underscores.",
)


class User(AbstractUser):
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
