from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def display_score(post):
    hide_minutes = getattr(post.community, "vote_hide_minutes", 0)
    if (timezone.now() - post.created_at).total_seconds() < hide_minutes * 60:
        return "•"
    return post.score


@register.filter
def timesince_compact(value):
    delta = timezone.now() - value
    seconds = int(delta.total_seconds())
    if seconds < 3600:
        return f"{max(seconds // 60, 1)}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"
