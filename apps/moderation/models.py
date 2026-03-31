from django.db import models


class ModQueueItem(models.Model):
    class Status(models.TextChoices):
        NEEDS_REVIEW = "needs_review", "Needs Review"
        REPORTED = "reported", "Reported"
        REMOVED = "removed", "Removed"
        APPROVED = "approved", "Approved"

    class ContentType(models.TextChoices):
        POST = "post", "Post"
        COMMENT = "comment", "Comment"

    community = models.ForeignKey("communities.Community", on_delete=models.CASCADE)
    content_type = models.CharField(max_length=10, choices=ContentType.choices)
    post = models.ForeignKey("posts.Post", null=True, blank=True, on_delete=models.CASCADE)
    comment = models.ForeignKey("posts.Comment", null=True, blank=True, on_delete=models.CASCADE)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.NEEDS_REVIEW)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        indexes = [models.Index(fields=["community", "status", "-created_at"])]


class Report(models.Model):
    reporter = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    post = models.ForeignKey("posts.Post", null=True, blank=True, on_delete=models.CASCADE)
    comment = models.ForeignKey("posts.Comment", null=True, blank=True, on_delete=models.CASCADE)
    reason = models.CharField(max_length=100)
    details = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    queue_item = models.ForeignKey(ModQueueItem, null=True, on_delete=models.SET_NULL)


class ModAction(models.Model):
    class ActionType(models.TextChoices):
        REMOVE_POST = "remove_post", "Remove Post"
        APPROVE_POST = "approve_post", "Approve Post"
        REMOVE_COMMENT = "remove_comment", "Remove Comment"
        APPROVE_COMMENT = "approve_comment", "Approve Comment"
        LOCK_POST = "lock_post", "Lock Post"
        STICKY_POST = "sticky_post", "Sticky Post"
        BAN_USER = "ban_user", "Ban User"
        UNBAN_USER = "unban_user", "Unban User"
        AGENT_FLAG = "agent_flag", "Agent Flag"
        AGENT_REMOVE = "agent_remove", "Agent Remove"
        AGENT_WARN = "agent_warn", "Agent Warn"

    community = models.ForeignKey("communities.Community", on_delete=models.CASCADE)
    moderator = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True)
    is_agent_action = models.BooleanField(default=False)
    action_type = models.CharField(max_length=30, choices=ActionType.choices)
    target_post = models.ForeignKey("posts.Post", null=True, blank=True, on_delete=models.SET_NULL)
    target_comment = models.ForeignKey("posts.Comment", null=True, blank=True, on_delete=models.SET_NULL)
    target_user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mod_actions_received",
    )
    reason_code = models.CharField(max_length=50, blank=True)
    reason_text = models.TextField(blank=True)
    details_json = models.JSONField(default=dict, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["community", "-created_at"]),
            models.Index(fields=["moderator", "-created_at"]),
        ]


class RemovalReason(models.Model):
    community = models.ForeignKey("communities.Community", on_delete=models.CASCADE, related_name="removal_reasons")
    code = models.CharField(max_length=50)
    title = models.CharField(max_length=100)
    message_md = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        unique_together = ("community", "code")


class Ban(models.Model):
    community = models.ForeignKey("communities.Community", on_delete=models.CASCADE)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    banned_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="bans_issued",
    )
    reason = models.TextField(blank=True)
    is_permanent = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("community", "user")


class CommunityAgentSettings(models.Model):
    community = models.OneToOneField(
        "communities.Community",
        on_delete=models.CASCADE,
        related_name="agent_settings",
    )
    auto_remove_threshold = models.FloatField(default=0.9)
    allow_auto_remove = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"Agent settings for c/{self.community.slug}"


class ModMail(models.Model):
    community = models.ForeignKey("communities.Community", on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]


class ModMailMessage(models.Model):
    thread = models.ForeignKey(ModMail, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True)
    body_md = models.TextField()
    body_html = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_mod_reply = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
