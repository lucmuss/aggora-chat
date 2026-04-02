from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time
from urllib.parse import quote

from django.conf import settings

from apps.communities.models import CommunityMembership


def generate_totp_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def normalize_totp_code(code: str) -> str:
    return "".join(char for char in (code or "") if char.isdigit())


def _normalized_secret(secret: str) -> bytes:
    padding = "=" * (-len(secret) % 8)
    return base64.b32decode(f"{secret}{padding}", casefold=True)


def _totp_at(secret: str, counter: int, digits: int = 6) -> str:
    key = _normalized_secret(secret)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**digits)
    return str(code_int).zfill(digits)


def verify_totp(secret: str, code: str, *, at_time: int | None = None, period: int = 30, window: int = 1) -> bool:
    normalized_code = normalize_totp_code(code)
    if not secret or len(normalized_code) != 6:
        return False
    now = at_time if at_time is not None else int(time.time())
    counter = now // period
    for delta in range(-window, window + 1):
        if hmac.compare_digest(_totp_at(secret, counter + delta), normalized_code):
            return True
    return False


def build_totp_uri(user) -> str:
    issuer = quote(settings.APP_NAME)
    account = quote(user.email or user.handle or user.username)
    return f"otpauth://totp/{issuer}:{account}?secret={user.mfa_totp_secret}&issuer={issuer}"


def user_requires_mfa(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    is_mod_or_owner = CommunityMembership.objects.filter(
        user=user,
        role__in=[CommunityMembership.Role.MODERATOR, CommunityMembership.Role.OWNER],
    ).exists()
    return (user.is_staff or is_mod_or_owner) and not user.mfa_totp_enabled
