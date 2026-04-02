from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.communities.models import Community
from apps.posts.models import Comment, Post

from .forms import ModMailCreateForm, ModMailReplyForm, RemovalReasonForm
from .models import ModAction, ModMail, ModQueueItem
from .permissions import ModPermission, has_mod_permission
from .services import (
    create_mod_mail,
    create_mod_mail_reply,
    execute_ban,
    execute_mod_action,
    submit_report,
)


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
    
    try:
        execute_mod_action(
            moderator=request.user,
            community=community,
            action_type=action_type,
            post_id=request.POST.get("post_id"),
            comment_id=request.POST.get("comment_id"),
            reason_code=request.POST.get("reason_code", ""),
            reason_text=request.POST.get("reason_text", ""),
        )
    except ObjectDoesNotExist:
        return redirect("mod_queue", community_slug=community_slug)

    if request.htmx:
        return render(request, "moderation/partials/queue_item_resolved.html", {"action_type": action_type})
    return redirect("mod_queue", community_slug=community_slug)


@require_POST
@login_required
def report_content(request):
    try:
        report, community, post, comment = submit_report(
            reporter=request.user,
            post_id=request.POST.get("post_id"),
            comment_id=request.POST.get("comment_id"),
            reason=request.POST.get("reason", "other"),
            details=request.POST.get("details", "")
        )
    except ObjectDoesNotExist:
        raise PermissionDenied

    if request.htmx:
        return render(request, "moderation/partials/report_success.html")
    if post:
        return redirect(
            "post_detail",
            community_slug=community.slug,
            post_id=post.id,
            slug=post.slug,
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
    
    ban = execute_ban(
        moderator=request.user,
        community=community,
        target_user=target_user,
        duration_days=int(request.POST.get("duration", 0) or 0),
        reason=request.POST.get("reason", ""),
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
    is_mod = has_mod_permission(request.user, community, ModPermission.MOD_MAIL)
    
    if not (is_mod or request.user == thread.created_by):
        raise PermissionDenied

    if request.method == "POST":
        form = ModMailReplyForm(request.POST)
        if form.is_valid():
            create_mod_mail_reply(
                author=request.user,
                thread=thread,
                body_md=form.cleaned_data["body_md"],
                is_mod_reply=is_mod,
            )
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
            thread = create_mod_mail(
                creator=request.user,
                community=community,
                body_md=form.cleaned_data["body_md"],
                title=form.cleaned_data["subject"],
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
