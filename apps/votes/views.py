from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.common.celery import dispatch_task
from apps.communities.services import can_view_community
from apps.posts.models import Comment, Post

from .models import ContentAward, SavedPost, Vote
from .services import AwardError, give_content_award
from .tasks import recalculate_comment_vote_totals, recalculate_karma, recalculate_post_vote_totals


@require_POST
@login_required
def vote(request):
    post_id = request.POST.get("post_id")
    comment_id = request.POST.get("comment_id")
    value = int(request.POST.get("value", "0"))

    if post_id:
        target = get_object_or_404(Post.objects.for_listing(), pk=post_id)
        existing = Vote.objects.filter(user=request.user, post=target).first()
        target_type = "post"
    else:
        target = get_object_or_404(Comment.objects.select_related("post", "author"), pk=comment_id)
        existing = Vote.objects.filter(user=request.user, comment=target).first()
        target_type = "comment"

    if existing:
        if existing.value == value:
            existing.delete()
            new_value = 0
        else:
            existing.value = value
            existing.save(update_fields=["value"])
            new_value = value
    else:
        Vote.objects.create(user=request.user, value=value, post_id=post_id, comment_id=comment_id)
        new_value = value

    if post_id:
        dispatch_task(recalculate_post_vote_totals, post_id)
        if target.author_id:
            dispatch_task(recalculate_karma, target.author_id)
    else:
        dispatch_task(recalculate_comment_vote_totals, comment_id)
        if target.author_id:
            dispatch_task(recalculate_karma, target.author_id)

    target.refresh_from_db()
    layout = "inline" if target_type == "comment" else "stacked"
    return render(
        request,
        "votes/partials/vote_widget.html",
        {"target": target, "target_type": target_type, "user_vote": new_value, "layout": layout},
    )


@require_POST
@login_required
def toggle_save(request, post_id):
    post = get_object_or_404(Post.objects.select_related("community"), pk=post_id)
    if not can_view_community(request.user, post.community):
        return HttpResponseForbidden("This post is not available in your current community access scope.")
    saved, created = SavedPost.objects.get_or_create(user=request.user, post=post)
    if not created:
        saved.delete()
        is_saved = False
    else:
        is_saved = True
    return render(request, "votes/partials/save_button.html", {"post": post, "is_saved": is_saved})


@require_POST
@login_required
def update_saved_post_status(request, post_id):
    saved = get_object_or_404(
        SavedPost.objects.select_related("post", "post__community"),
        user=request.user,
        post_id=post_id,
    )
    action = request.POST.get("action", "status")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    if action == "remove":
        saved.delete()
        return redirect(next_url)

    status = request.POST.get("status", SavedPost.QueueStatus.UNREAD)
    allowed_statuses = {choice for choice, _ in SavedPost.QueueStatus.choices}
    if status not in allowed_statuses:
        return HttpResponseForbidden("Unsupported reader queue status.")
    saved.status = status
    saved.save(update_fields=["status"])
    return redirect(next_url)


@require_POST
@login_required
def give_award(request):
    post_id = request.POST.get("post_id")
    comment_id = request.POST.get("comment_id")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"

    if post_id:
        post = get_object_or_404(Post.objects.select_related("community", "author"), pk=post_id)
        if not can_view_community(request.user, post.community):
            return HttpResponseForbidden("This post is not available in your current community access scope.")
        try:
            give_content_award(giver=request.user, post=post)
            messages.success(request, "Award sent. You helped this thread stand out.")
        except AwardError as exc:
            messages.error(request, str(exc))
    elif comment_id:
        comment = get_object_or_404(Comment.objects.select_related("post__community", "author"), pk=comment_id)
        if not can_view_community(request.user, comment.post.community):
            return HttpResponseForbidden("This comment is not available in your current community access scope.")
        try:
            give_content_award(giver=request.user, comment=comment)
            messages.success(request, "Award sent. You highlighted a thoughtful reply.")
        except AwardError as exc:
            messages.error(request, str(exc))
    else:
        return HttpResponseForbidden("Missing content target.")

    return redirect(next_url)
