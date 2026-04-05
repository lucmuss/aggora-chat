from django.db.models import Count, Q, Sum

from apps.common.celery import dispatch_task
from apps.search.tasks import index_post_task
from celery import shared_task


@shared_task
def recalculate_post_vote_totals(post_id):
    from apps.posts.models import Post
    from apps.posts.services import hot_score

    from .models import Vote

    totals = Vote.objects.filter(post_id=post_id).aggregate(
        ups=Count("id", filter=Q(value=1)),
        downs=Count("id", filter=Q(value=-1)),
    )
    post = Post.objects.get(pk=post_id)
    post.upvote_count = totals["ups"] or 0
    post.downvote_count = totals["downs"] or 0
    post.score = post.upvote_count - post.downvote_count
    post.hot_score = hot_score(post.upvote_count, post.downvote_count, post.created_at)
    post.save(update_fields=["upvote_count", "downvote_count", "score", "hot_score", "body_html"])
    dispatch_task(index_post_task, post_id)


@shared_task
def recalculate_comment_vote_totals(comment_id):
    from apps.posts.models import Comment

    from .models import Vote

    totals = Vote.objects.filter(comment_id=comment_id).aggregate(
        ups=Count("id", filter=Q(value=1)),
        downs=Count("id", filter=Q(value=-1)),
    )
    comment = Comment.objects.get(pk=comment_id)
    comment.upvote_count = totals["ups"] or 0
    comment.downvote_count = totals["downs"] or 0
    comment.score = comment.upvote_count - comment.downvote_count
    comment.save(update_fields=["upvote_count", "downvote_count", "score", "body_html"])


@shared_task
def recalculate_karma(user_id):
    from apps.accounts.models import User

    from .models import Vote

    post_karma = Vote.objects.filter(post__author_id=user_id, post__isnull=False).aggregate(total=Sum("value"))["total"] or 0
    comment_karma = Vote.objects.filter(comment__author_id=user_id, comment__isnull=False).aggregate(total=Sum("value"))["total"] or 0
    User.objects.filter(pk=user_id).update(post_karma=post_karma, comment_karma=comment_karma)
