from __future__ import annotations

import re
from hashlib import blake2s
from pathlib import Path, PurePosixPath
from secrets import token_bytes

from django.utils import timezone
from django.utils.deconstruct import deconstructible

HASHED_FILENAME_RE = re.compile(r"^\d{8}-[0-9a-f]{8,16}\.[a-z0-9]+$")


def _normalized_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def _short_hash(filename: str, *, hash_length: int, seed: bytes | None = None) -> str:
    digest = blake2s(digest_size=16)
    digest.update(seed if seed is not None else token_bytes(16))
    digest.update(filename.encode("utf-8", "ignore"))
    return digest.hexdigest()[:hash_length]


def build_hashed_upload_path(
    folder: str,
    filename: str,
    *,
    hash_length: int = 12,
    now=None,
    seed: bytes | None = None,
) -> str:
    folder = folder.strip("/").replace("\\", "/")
    hash_length = max(8, min(hash_length, 16))
    now = now or timezone.now()
    day_path = now.strftime("%Y/%m/%d")
    day_stamp = now.strftime("%Y%m%d")
    short_hash = _short_hash(filename, hash_length=hash_length, seed=seed)
    shard_one = short_hash[:2]
    shard_two = short_hash[2:4]
    extension = _normalized_extension(filename)
    return f"{folder}/{day_path}/{shard_one}/{shard_two}/{day_stamp}-{short_hash}{extension}"


def is_hashed_upload_path(name: str, *, root_prefix: str | None = None) -> bool:
    normalized_name = name.lstrip("/").replace("\\", "/")
    parts = list(PurePosixPath(normalized_name).parts)
    if root_prefix:
        prefix_parts = list(PurePosixPath(root_prefix.strip("/")).parts)
        if parts[: len(prefix_parts)] != prefix_parts:
            return False
        parts = parts[len(prefix_parts) :]
    if len(parts) != 7:
        return False

    _, year, month, day, shard_one, shard_two, filename = parts
    return (
        len(year) == 4
        and year.isdigit()
        and len(month) == 2
        and month.isdigit()
        and len(day) == 2
        and day.isdigit()
        and len(shard_one) == 2
        and all(char in "0123456789abcdef" for char in shard_one)
        and len(shard_two) == 2
        and all(char in "0123456789abcdef" for char in shard_two)
        and HASHED_FILENAME_RE.match(filename) is not None
    )


@deconstructible
class HashedUploadTo:
    def __init__(self, folder: str, *, hash_length: int = 12):
        self.folder = folder.strip("/").replace("\\", "/")
        self.hash_length = max(8, min(hash_length, 16))

    def __call__(self, instance, filename: str) -> str:
        return build_hashed_upload_path(self.folder, filename, hash_length=self.hash_length)
