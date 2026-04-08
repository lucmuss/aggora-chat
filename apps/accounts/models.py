from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.common.image_variants import optimized_image_url
from apps.common.upload_paths import HashedUploadTo

handle_validator = RegexValidator(
    regex=r"^[a-z0-9_]{3,30}$",
    message="Use 3-30 lowercase letters, numbers, or underscores.",
)


class User(AbstractUser):
    class ProfileVisibility(models.TextChoices):
        PUBLIC = "public", "Public"
        MEMBERS = "members", "Signed-in members"
        PRIVATE = "private", "Private"

    class PreferredTheme(models.TextChoices):
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"

    class PreferredLanguage(models.TextChoices):
        ENGLISH = "en", "English"

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
    avatar = models.ImageField(upload_to=HashedUploadTo("original/avatars"), blank=True)
    banner = models.ImageField(upload_to=HashedUploadTo("original/profile_banners"), blank=True)
    birth_date = models.DateField(null=True, blank=True)
    country = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
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
    allow_nsfw_content = models.BooleanField(default=False)
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
    first_post_share_at = models.DateTimeField(null=True, blank=True)
    preferred_theme = models.CharField(
        max_length=10,
        choices=PreferredTheme.choices,
        default=PreferredTheme.LIGHT,
    )
    preferred_language = models.CharField(
        max_length=8,
        choices=PreferredLanguage.choices,
        default=PreferredLanguage.ENGLISH,
    )

    def total_karma(self) -> int:
        return self.post_karma + self.comment_karma

    @property
    def awards_received_count(self) -> int:
        post_total = self.posts.aggregate(total=models.Sum("award_count")).get("total") or 0
        comment_total = self.comment_set.aggregate(total=models.Sum("award_count")).get("total") or 0
        return post_total + comment_total

    @property
    def age(self) -> int | None:
        if not self.birth_date:
            return None
        today = timezone.localdate()
        years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return max(years, 0)

    def __str__(self) -> str:
        return self.handle or self.email or self.username

    @property
    def avatar_original_url(self) -> str | None:
        return self.avatar.url if self.avatar else None

    @property
    def banner_original_url(self) -> str | None:
        return self.banner.url if self.banner else None

    @property
    def avatar_optimized_url(self) -> str | None:
        return optimized_image_url(self.avatar)

    @property
    def banner_optimized_url(self) -> str | None:
        return optimized_image_url(self.banner)

    @property
    def avatar_optimized_srcset(self) -> str:
        from apps.common.image_variants import optimized_image_srcset

        return optimized_image_srcset(self.avatar)

    @property
    def banner_optimized_srcset(self) -> str:
        from apps.common.image_variants import optimized_image_srcset

        return optimized_image_srcset(self.banner)


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
        MENTION = "mention", "Mention"
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


class UserBadge(models.Model):
    class BadgeCode(models.TextChoices):
        PROFILE_READY = "profile_ready", "Profile Ready"
        FIRST_STEPS = "first_steps", "First Steps"
        FIRST_POST = "first_post", "First Post"
        FIRST_COMMENT = "first_comment", "First Comment"
        FIRST_REFERRAL = "first_referral", "First Referral"
        CREW_BUILDER = "crew_builder", "Crew Builder"
        CHALLENGE_ACCEPTED = "challenge_accepted", "Challenge Accepted"
        MOMENTUM = "momentum", "Momentum"

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="badges")
    code = models.CharField(max_length=32, choices=BadgeCode.choices)
    title = models.CharField(max_length=80)
    description = models.CharField(max_length=160, blank=True)
    icon = models.CharField(max_length=8, default="★")
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-awarded_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "code"], name="accounts_unique_user_badge_code"),
        ]

    def __str__(self) -> str:
        return f"{self.user}: {self.title}"
