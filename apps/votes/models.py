from django.db import models
from django.utils import timezone


class Vote(models.Model):
    class VoteType(models.IntegerChoices):
        UPVOTE = 1, "Upvote"
        DOWNVOTE = -1, "Downvote"

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    post = models.ForeignKey("posts.Post", null=True, blank=True, on_delete=models.CASCADE)
    comment = models.ForeignKey("posts.Comment", null=True, blank=True, on_delete=models.CASCADE)
    value = models.SmallIntegerField(choices=VoteType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                condition=models.Q(post__isnull=False),
                name="unique_post_vote",
            ),
            models.UniqueConstraint(
                fields=["user", "comment"],
                condition=models.Q(comment__isnull=False),
                name="unique_comment_vote",
            ),
            models.CheckConstraint(
                condition=(
                    (models.Q(post__isnull=False) & models.Q(comment__isnull=True))
                    | (models.Q(post__isnull=True) & models.Q(comment__isnull=False))
                ),
                name="vote_targets_exactly_one_object",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "post"]),
            models.Index(fields=["user", "comment"]),
        ]


class SavedPost(models.Model):
    class QueueStatus(models.TextChoices):
        UNREAD = "unread", "Unread"
        READING = "reading", "Reading"
        DONE = "done", "Done"

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="saved_posts")
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=QueueStatus.choices, default=QueueStatus.UNREAD)

    class Meta:
        unique_together = ("user", "post")


class ContentAward(models.Model):
    MONTHLY_LIMIT = 3

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="content_awards_given")
    recipient = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="content_awards_received")
    post = models.ForeignKey("posts.Post", null=True, blank=True, on_delete=models.CASCADE, related_name="awards")
    comment = models.ForeignKey("posts.Comment", null=True, blank=True, on_delete=models.CASCADE, related_name="awards")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                condition=models.Q(post__isnull=False),
                name="unique_post_award",
            ),
            models.UniqueConstraint(
                fields=["user", "comment"],
                condition=models.Q(comment__isnull=False),
                name="unique_comment_award",
            ),
            models.CheckConstraint(
                condition=(
                    (models.Q(post__isnull=False) & models.Q(comment__isnull=True))
                    | (models.Q(post__isnull=True) & models.Q(comment__isnull=False))
                ),
                name="award_targets_exactly_one_object",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]

    @classmethod
    def awards_given_this_month(cls, user, *, now=None):
        if user is None or not getattr(user, "is_authenticated", False):
            return 0
        now = now or timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return cls.objects.filter(user=user, created_at__gte=month_start).count()

    @classmethod
    def remaining_for_user(cls, user, *, now=None):
        if user is None or not getattr(user, "is_authenticated", False):
            return 0
        return max(0, cls.MONTHLY_LIMIT - cls.awards_given_this_month(user, now=now))
