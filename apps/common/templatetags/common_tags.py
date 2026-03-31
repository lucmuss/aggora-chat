from django import template


register = template.Library()


@register.filter
def get_item(mapping, key):
    if not mapping:
        return 0
    return mapping.get(key, 0)


@register.filter
def split(value, separator):
    return value.split(separator)


@register.filter
def contains(items, key):
    if not items:
        return False
    return key in items


@register.filter
def pairs(data):
    """
    Groups a list into pairs.
    Example: ['a', 'b', 'c', 'd'] -> [('a', 'b'), ('c', 'd')]
    """
    it = iter(data)
    return zip(it, it)

from django.utils import timezone
import datetime

@register.filter
def timesince_compact(dt):
    if not isinstance(dt, datetime.datetime):
        return ""
    now = timezone.now()
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m"
    elif seconds < 86400:
        return f"{int(seconds // 3600)}h"
    elif seconds < 31536000:
        return f"{int(seconds // 86400)}d"
    else:
        return f"{int(seconds // 31536000)}y"
