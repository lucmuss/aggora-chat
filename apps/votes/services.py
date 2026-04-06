from __future__ import annotations

from django.db import transaction
from django.db.models import F

from apps.posts.models import Comment, Post

from .models import ContentAward


class AwardError(ValueError):
    pass


@transaction.atomic
def give_content_award(*, giver, post: Post | None = None, comment: Comment | None = None) -> ContentAward:
    if (post is None and comment is None) or (post is not None and comment is not None):
        raise AwardError("Awards must target exactly one piece of content.")

    target = post or comment
    recipient = getattr(target, "author", None)
    if recipient is None:
        raise AwardError("You cannot award deleted content.")
    if recipient == giver:
        raise AwardError("You cannot award your own content.")
    if ContentAward.remaining_for_user(giver) <= 0:
        raise AwardError("You have used all three awards for this month.")

    existing_filter = {"user": giver, "post": post} if post is not None else {"user": giver, "comment": comment}
    if ContentAward.objects.filter(**existing_filter).exists():
        raise AwardError("You already awarded this.")

    award = ContentAward.objects.create(
        user=giver,
        recipient=recipient,
        post=post,
        comment=comment,
    )

    if post is not None:
        Post.objects.filter(pk=post.pk).update(award_count=F("award_count") + 1)
    else:
        Comment.objects.filter(pk=comment.pk).update(award_count=F("award_count") + 1)

    return award
