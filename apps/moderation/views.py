from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.common.markdown import render_markdown
from apps.communities.models import Community
from apps.posts.models import Comment, Post
from apps.search.tasks import index_post_task

from .forms import ModMailCreateForm, ModMailReplyForm, RemovalReasonForm
from .models import Ban, ModAction, ModMail, ModMailMessage, ModQueueItem, Report, RemovalReason
from .permissions import ModPermission, has_mod_permission


@login_required
def mod_queue(request, community_slug):
    community = get_object_or_404(Community, slug=community_slug)
    if not has_mod_permission(request.user, community, ModPermission.VIEW_MOD_QUEUE):
        raise PermissionDenied

    status_filter = request.GET.get("status", ModQueueItem.Status.NEEDS_REVIEW)
    items = (
        ModQueueItem.objects.filter(community=community, status=status_filter)
        .select_related("post", "comment", "post__author", "comment__author", "resolved_by")
        .prefetch_related("report_set")
        .order_by("-created_at")[:50]
    )
    return render(
        request,
        "moderation/queue.html",
        {
            "community": community,
            "items": items,
            "status_filter": status_filter,
            "removal_reasons": community.removal_reasons.all(),
        },
    )


@login_required
def mod_log(request, community_slug):
    community = get_object_or_404(Community, slug=community_slug)
    if not has_mod_permission(request.user, community, ModPermission.VIEW_MOD_LOG):
        raise PermissionDenied

    actions = (
        ModAction.objects.filter(community=community)
        .select_related("moderator", "target_post", "target_comment", "target_user")
        .order_by("-created_at")[:100]
    )
    return render(request, "moderation/log.html", {"community": community, "actions": actions})


@require_POST
@login_required
def mod_action(request, community_slug):
    community = get_object_or_404(Community, slug=community_slug)
    if not has_mod_permission(request.user, community, ModPermission.MANAGE_POSTS):
        raise PermissionDenied

    action_type = request.POST.get("action_type")
    post_id = request.POST.get("post_id")
    comment_id = request.POST.get("comment_id")
    reason_code = request.POST.get("reason_code", "")
    reason_text = request.POST.get("reason_text", "")

    target_post = None
    target_comment = None

    if post_id:
        target_post = get_object_or_404(Post, pk=post_id, community=community)
    if comment_id:
        target_comment = get_object_or_404(Comment, pk=comment_id, post__community=community)

    if action_type == "remove_post" and target_post:
        target_post.is_removed = True
        target_post.removed_reason = reason_text
        target_post.save(update_fields=["is_removed", "removed_reason", "body_html"])
        index_post_task(target_post.pk)
    elif action_type == "approve_post" and target_post:
        target_post.is_removed = False
        target_post.removed_reason = ""
        target_post.save(update_fields=["is_removed", "removed_reason", "body_html"])
        index_post_task(target_post.pk)
    elif action_type == "lock_post" and target_post:
        target_post.is_locked = True
        target_post.save(update_fields=["is_locked", "body_html"])
    elif action_type == "sticky_post" and target_post:
        target_post.is_stickied = True
        target_post.save(update_fields=["is_stickied", "body_html"])
    elif action_type == "remove_comment" and target_comment:
        target_comment.is_removed = True
        target_comment.save(update_fields=["is_removed", "body_html"])
    elif action_type == "approve_comment" and target_comment:
        target_comment.is_removed = False
        target_comment.save(update_fields=["is_removed", "body_html"])

    ModAction.objects.create(
        community=community,
        moderator=request.user,
        is_agent_action=request.user.is_agent,
        action_type=action_type,
        target_post=target_post,
        target_comment=target_comment,
        reason_code=reason_code,
        reason_text=reason_text,
    )

    queue_item = ModQueueItem.objects.filter(
        community=community,
        post_id=post_id or None,
        comment_id=comment_id or None,
    ).order_by("-created_at").first()
    if queue_item:
        queue_item.status = (
            ModQueueItem.Status.REMOVED if "remove" in action_type else ModQueueItem.Status.APPROVED
        )
        queue_item.resolved_by = request.user
        queue_item.resolved_at = timezone.now()
        queue_item.save(update_fields=["status", "resolved_by", "resolved_at"])

    if request.htmx:
        return render(request, "moderation/partials/queue_item_resolved.html", {"action_type": action_type})
    return redirect("mod_queue", community_slug=community_slug)


@require_POST
@login_required
def report_content(request):
    post_id = request.POST.get("post_id")
    comment_id = request.POST.get("comment_id")
    reason = request.POST.get("reason", "other")
    details = request.POST.get("details", "")

    community = None
    if post_id:
        post = get_object_or_404(Post, pk=post_id)
        community = post.community
    else:
        comment = get_object_or_404(Comment, pk=comment_id)
        community = comment.post.community

    queue_item, _ = ModQueueItem.objects.get_or_create(
        community=community,
        post_id=post_id or None,
        comment_id=comment_id or None,
        defaults={
            "status": ModQueueItem.Status.REPORTED,
            "content_type": ModQueueItem.ContentType.POST if post_id else ModQueueItem.ContentType.COMMENT,
        },
    )

    Report.objects.create(
        reporter=request.user,
        post_id=post_id or None,
        comment_id=comment_id or None,
        reason=reason,
        details=details,
        queue_item=queue_item,
    )

    if request.htmx:
        return render(request, "moderation/partials/report_success.html")
    if post_id:
        return redirect(
            "post_detail",
            community_slug=community.slug,
            post_id=post_id,
            slug=get_object_or_404(Post, pk=post_id).slug,
        )
    return redirect(
        "post_detail",
        community_slug=community.slug,
        post_id=comment.post_id,
        slug=comment.post.slug,
    )


@require_POST
@login_required
def ban_user(request, community_slug):
    community = get_object_or_404(Community, slug=community_slug)
    if not has_mod_permission(request.user, community, ModPermission.MANAGE_USERS):
        raise PermissionDenied

    target_user = get_object_or_404(User, handle=request.POST.get("handle"))
    duration_days = int(request.POST.get("duration", 0) or 0)
    reason = request.POST.get("reason", "")

    ban, _ = Ban.objects.update_or_create(
        community=community,
        user=target_user,
        defaults={
            "banned_by": request.user,
            "reason": reason,
            "is_permanent": duration_days == 0,
            "expires_at": timezone.now() + timedelta(days=duration_days) if duration_days else None,
        },
    )
    ModAction.objects.create(
        community=community,
        moderator=request.user,
        action_type=ModAction.ActionType.BAN_USER,
        target_user=target_user,
        reason_text=reason,
        details_json={"duration_days": duration_days, "permanent": duration_days == 0},
    )

    if request.htmx:
        return render(request, "moderation/partials/ban_confirmed.html", {"ban": ban})
    return redirect("mod_log", community_slug=community_slug)


@login_required
def mod_mail_list(request, community_slug):
    community = get_object_or_404(Community, slug=community_slug)
    if not has_mod_permission(request.user, community, ModPermission.MOD_MAIL):
        raise PermissionDenied

    threads = ModMail.objects.filter(community=community).select_related("created_by")[:100]
    return render(request, "moderation/mail_list.html", {"community": community, "threads": threads})


@login_required
def mod_mail_thread(request, community_slug, thread_id):
    community = get_object_or_404(Community, slug=community_slug)
    thread = get_object_or_404(ModMail.objects.filter(community=community), pk=thread_id)
    if not (
        has_mod_permission(request.user, community, ModPermission.MOD_MAIL)
        or request.user == thread.created_by
    ):
        raise PermissionDenied

    if request.method == "POST":
        form = ModMailReplyForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.thread = thread
            reply.author = request.user
            reply.is_mod_reply = has_mod_permission(request.user, community, ModPermission.MOD_MAIL)
            reply.save()
            return redirect("mod_mail_thread", community_slug=community.slug, thread_id=thread.id)
    else:
        form = ModMailReplyForm()

    return render(
        request,
        "moderation/mail_thread.html",
        {"community": community, "thread": thread, "form": form},
    )


@login_required
def mod_mail_create(request, community_slug):
    community = get_object_or_404(Community, slug=community_slug)
    if request.method == "POST":
        form = ModMailCreateForm(request.POST)
        if form.is_valid():
            thread = form.save(commit=False)
            thread.community = community
            thread.created_by = request.user
            thread.save()
            ModMailMessage.objects.create(
                thread=thread,
                author=request.user,
                body_md=form.cleaned_data["body_md"],
                body_html=render_markdown(form.cleaned_data["body_md"]),
                is_mod_reply=False,
            )
            return redirect("mod_mail_thread", community_slug=community.slug, thread_id=thread.id)
    else:
        form = ModMailCreateForm()

    return render(request, "moderation/mail_create.html", {"community": community, "form": form})


@login_required
def removal_reasons_manage(request, community_slug):
    community = get_object_or_404(Community, slug=community_slug)
    if not has_mod_permission(request.user, community, ModPermission.MANAGE_SETTINGS):
        raise PermissionDenied

    if request.method == "POST":
        form = RemovalReasonForm(request.POST)
        if form.is_valid():
            removal_reason = form.save(commit=False)
            removal_reason.community = community
            removal_reason.save()
            return redirect("removal_reasons_manage", community_slug=community.slug)
    else:
        form = RemovalReasonForm()

    return render(
        request,
        "moderation/removal_reasons.html",
        {"community": community, "form": form, "reasons": community.removal_reasons.all()},
    )
