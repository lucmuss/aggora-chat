from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.utils import timezone

from apps.accounts.models import User
from apps.common.markdown import render_markdown
from apps.communities.models import Community
from apps.posts.models import Comment, Post
from apps.search.tasks import index_post_task

from .models import Ban, ModAction, ModMail, ModMailMessage, ModQueueItem, Report


def execute_mod_action(
    moderator: User,
    community: Community,
    action_type: str,
    post_id: str | None = None,
    comment_id: str | None = None,
    reason_code: str = "",
    reason_text: str = "",
):
    """Executes a moderation action on a post or comment and logs the action."""
    target_post = None
    target_comment = None

    if post_id:
        target_post = Post.objects.get(pk=post_id, community=community)
    elif comment_id:
        target_comment = Comment.objects.get(pk=comment_id, post__community=community)

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
    elif action_type == "unlock_post" and target_post:
        target_post.is_locked = False
        target_post.save(update_fields=["is_locked", "body_html"])
    elif action_type == "sticky_post" and target_post:
        target_post.is_stickied = True
        target_post.save(update_fields=["is_stickied", "body_html"])
    elif action_type == "unsticky_post" and target_post:
        target_post.is_stickied = False
        target_post.save(update_fields=["is_stickied", "body_html"])
    elif action_type == "remove_comment" and target_comment:
        target_comment.is_removed = True
        target_comment.save(update_fields=["is_removed", "body_html"])
    elif action_type == "approve_comment" and target_comment:
        target_comment.is_removed = False
        target_comment.save(update_fields=["is_removed", "body_html"])

    ModAction.objects.create(
        community=community,
        moderator=moderator,
        is_agent_action=moderator.is_agent,
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
        queue_item.resolved_by = moderator
        queue_item.resolved_at = timezone.now()
        queue_item.save(update_fields=["status", "resolved_by", "resolved_at"])


def submit_report(
    reporter: User,
    post_id: str | None,
    comment_id: str | None,
    reason: str,
    details: str,
) -> tuple[Report, Optional[Community], Optional[Post], Optional[Comment]]:
    """Submits a content report to the moderation queue."""
    community = None
    post = None
    comment = None

    if post_id:
        post = Post.objects.get(pk=post_id)
        community = post.community
    else:
        comment = Comment.objects.get(pk=comment_id)
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

    report = Report.objects.create(
        reporter=reporter,
        post_id=post_id or None,
        comment_id=comment_id or None,
        reason=reason,
        details=details,
        queue_item=queue_item,
    )

    return report, community, post, comment


def execute_ban(
    moderator: User,
    community: Community,
    target_user: User,
    duration_days: int,
    reason: str,
) -> Ban:
    """Executes a ban on a user in a specific community."""
    ban, _ = Ban.objects.update_or_create(
        community=community,
        user=target_user,
        defaults={
            "banned_by": moderator,
            "reason": reason,
            "is_permanent": duration_days == 0,
            "expires_at": timezone.now() + timedelta(days=duration_days) if duration_days else None,
        },
    )

    ModAction.objects.create(
        community=community,
        moderator=moderator,
        action_type=ModAction.ActionType.BAN_USER,
        target_user=target_user,
        reason_text=reason,
        details_json={"duration_days": duration_days, "permanent": duration_days == 0},
    )

    return ban


def create_mod_mail(creator: User, community: Community, body_md: str, title: str) -> ModMail:
    """Creates a new mod mail thread."""
    thread = ModMail.objects.create(
        community=community,
        created_by=creator,
        subject=title,
    )
    ModMailMessage.objects.create(
        thread=thread,
        author=creator,
        body_md=body_md,
        body_html=render_markdown(body_md),
        is_mod_reply=False,
    )
    return thread


def create_mod_mail_reply(author: User, thread: ModMail, body_md: str, is_mod_reply: bool) -> ModMailMessage:
    """Creates a reply in a mod mail thread."""
    return ModMailMessage.objects.create(
        thread=thread,
        author=author,
        body_md=body_md,
        body_html=render_markdown(body_md),
        is_mod_reply=is_mod_reply,
    )
