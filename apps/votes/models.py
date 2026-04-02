from django.db import models


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
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="saved_posts")
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "post")
