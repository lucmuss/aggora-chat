from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

import pytest

from apps.accounts.models import User
from apps.communities.models import Community
from apps.posts.models import Post


@pytest.fixture(autouse=True)
def fixed_upload_hash(monkeypatch):
    monkeypatch.setattr("apps.common.upload_paths.token_bytes", lambda size: b"\x01" * size)
    monkeypatch.setattr(
        "apps.common.upload_paths.timezone.now",
        lambda: datetime(2026, 4, 8, 12, 30, tzinfo=dt_timezone.utc),
    )


@pytest.mark.parametrize(
    ("field_name", "instance", "original_name", "expected_path"),
    [
        (
            "avatar",
            User(username="upload_user", email="upload@example.com"),
            "Profile Photo.PNG",
            "original/avatars/2026/04/08/33/93/20260408-339300d4779d.png",
        ),
        (
            "banner",
            User(username="banner_user", email="banner@example.com"),
            "Header.JPG",
            "original/profile_banners/2026/04/08/3f/be/20260408-3fbe2e5c6220.jpg",
        ),
        (
            "image",
            Post(title="Uploaded", slug="uploaded"),
            "cover.JpEg",
            "original/post_images/2026/04/08/43/8c/20260408-438c43503e62.jpeg",
        ),
        (
            "icon",
            Community(name="Uploads", slug="uploads", title="Uploads"),
            "Icon.PNG",
            "original/community_icons/2026/04/08/a7/43/20260408-a743f6ada0b2.png",
        ),
        (
            "banner",
            Community(name="Uploads Two", slug="uploads-two", title="Uploads Two"),
            "hero-image.webp",
            "original/community_banners/2026/04/08/ed/b6/20260408-edb69a12dc5a.webp",
        ),
    ],
)
def test_uploads_use_dated_hashed_paths(field_name, instance, original_name, expected_path):
    field = instance._meta.get_field(field_name)
    filename = field.generate_filename(instance, original_name)

    assert filename == expected_path
