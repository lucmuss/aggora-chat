from __future__ import annotations

from hashlib import blake2s
from pathlib import Path
from secrets import token_bytes

from django.utils import timezone
from django.utils.deconstruct import deconstructible


def _normalized_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def _short_hash(filename: str, *, hash_length: int) -> str:
    digest = blake2s(digest_size=16)
    digest.update(token_bytes(16))
    digest.update(filename.encode("utf-8", "ignore"))
    return digest.hexdigest()[:hash_length]


@deconstructible
class HashedUploadTo:
    def __init__(self, folder: str, *, hash_length: int = 12):
        self.folder = folder.strip("/").replace("\\", "/")
        self.hash_length = max(8, min(hash_length, 16))

    def __call__(self, instance, filename: str) -> str:
        now = timezone.now()
        day_path = now.strftime("%Y/%m/%d")
        day_stamp = now.strftime("%Y%m%d")
        short_hash = _short_hash(filename, hash_length=self.hash_length)
        shard_one = short_hash[:2]
        shard_two = short_hash[2:4]
        extension = _normalized_extension(filename)
        return f"{self.folder}/{day_path}/{shard_one}/{shard_two}/{day_stamp}-{short_hash}{extension}"
