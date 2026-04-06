from __future__ import annotations

import re
from typing import Iterable

from django.contrib.auth import get_user_model

MENTION_PATTERN = re.compile(r"(?<![\w/`])@([A-Za-z0-9_]{3,30})\b")

User = get_user_model()


def extract_mentioned_handles(*chunks: str) -> list[str]:
    seen: list[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        for match in MENTION_PATTERN.finditer(chunk):
            handle = match.group(1).strip().lower()
            if handle and handle not in seen:
                seen.append(handle)
    return seen


def resolve_mentioned_users(*chunks: str, exclude_ids: Iterable[int] | None = None):
    handles = extract_mentioned_handles(*chunks)
    if not handles:
        return User.objects.none()
    queryset = User.objects.filter(handle__in=handles)
    if exclude_ids:
        queryset = queryset.exclude(pk__in=list(exclude_ids))
    return queryset
