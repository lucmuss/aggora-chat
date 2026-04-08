from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from PIL import Image

from apps.accounts.models import User
from apps.common.image_variants import iter_variant_names, optimized_image_srcset, variant_image_name
from apps.communities.models import Community
from apps.posts.models import Post

LOCAL_MEDIA_SETTINGS = override_settings(
    USE_S3=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)


def make_uploaded_image(name: str, *, size=(2400, 1600), image_format="PNG", color="#2563eb") -> SimpleUploadedFile:
    file_obj = BytesIO()
    Image.new("RGB", size, color=color).save(file_obj, format=image_format)
    file_obj.seek(0)
    return SimpleUploadedFile(name, file_obj.read(), content_type=f"image/{image_format.lower()}")


def image_size(path: Path) -> tuple[int, int]:
    image = Image.open(path)
    return image.size


@pytest.mark.django_db
class TestImageVariants:
    @LOCAL_MEDIA_SETTINGS
    def test_avatar_upload_creates_sm_md_lg_variants(self, settings, tmp_path, django_capture_on_commit_callbacks):
        settings.MEDIA_ROOT = tmp_path
        settings.LOCAL_MEDIA_ROOT = tmp_path
        settings.MEDIA_URL = "/media/"

        user = User.objects.create_user(
            username="variant_user",
            email="variant_user@example.com",
            password="password123",
            handle="variant_user",
        )

        with django_capture_on_commit_callbacks(execute=True):
            user.avatar = make_uploaded_image("profile.png", size=(1800, 1800))
            user.save(update_fields=["avatar"])

        variant_names = iter_variant_names(user.avatar.name)
        assert variant_names == [
            variant_image_name(user.avatar.name, "sm"),
            variant_image_name(user.avatar.name, "md"),
            variant_image_name(user.avatar.name, "lg"),
        ]
        for variant_name in variant_names:
            assert variant_name is not None
            assert (Path(tmp_path) / variant_name).exists()

        assert user.avatar_optimized_url == f"/media/{variant_image_name(user.avatar.name, 'md')}"
        assert user.avatar_optimized_srcset == optimized_image_srcset(user.avatar)
        assert "64w" in user.avatar_optimized_srcset
        assert "128w" in user.avatar_optimized_srcset
        assert "256w" in user.avatar_optimized_srcset

        assert image_size(Path(tmp_path) / variant_image_name(user.avatar.name, "sm"))[0] <= 64
        assert image_size(Path(tmp_path) / variant_image_name(user.avatar.name, "md"))[0] <= 128
        assert image_size(Path(tmp_path) / variant_image_name(user.avatar.name, "lg"))[0] <= 256

    @LOCAL_MEDIA_SETTINGS
    def test_post_image_upload_creates_responsive_webp_variants(self, settings, tmp_path, django_capture_on_commit_callbacks):
        settings.MEDIA_ROOT = tmp_path
        settings.LOCAL_MEDIA_ROOT = tmp_path
        settings.MEDIA_URL = "/media/"

        user = User.objects.create_user(
            username="variant_post_user",
            email="variant_post_user@example.com",
            password="password123",
            handle="variant_post_user",
        )
        community = Community.objects.create(
            name="Variant Community",
            slug="variant-community",
            title="Variant Community",
            creator=user,
        )

        with django_capture_on_commit_callbacks(execute=True):
            post = Post.objects.create(
                community=community,
                author=user,
                post_type=Post.PostType.IMAGE,
                title="Variant Post",
                image=make_uploaded_image("thread-image.jpeg", size=(2600, 2000), image_format="JPEG"),
            )

        assert post.image_optimized_url == f"/media/{variant_image_name(post.image.name, 'lg')}"
        assert "480w" in post.image_optimized_srcset
        assert "960w" in post.image_optimized_srcset
        assert "1600w" in post.image_optimized_srcset

        assert image_size(Path(tmp_path) / variant_image_name(post.image.name, "sm"))[0] <= 480
        assert image_size(Path(tmp_path) / variant_image_name(post.image.name, "md"))[0] <= 960
        assert image_size(Path(tmp_path) / variant_image_name(post.image.name, "lg"))[0] <= 1600

    @LOCAL_MEDIA_SETTINGS
    def test_backfill_command_generates_missing_variants(self, settings, tmp_path, django_capture_on_commit_callbacks):
        settings.MEDIA_ROOT = tmp_path
        settings.LOCAL_MEDIA_ROOT = tmp_path

        user = User.objects.create_user(
            username="variant_backfill",
            email="variant_backfill@example.com",
            password="password123",
            handle="variant_backfill",
        )

        with django_capture_on_commit_callbacks(execute=True):
            user.avatar = make_uploaded_image("backfill.png", size=(900, 900))
            user.save(update_fields=["avatar"])

        for variant_name in iter_variant_names(user.avatar.name):
            (Path(tmp_path) / variant_name).unlink()

        call_command("backfill_optimized_media_variants")

        for variant_name in iter_variant_names(user.avatar.name):
            assert (Path(tmp_path) / variant_name).exists()

    @LOCAL_MEDIA_SETTINGS
    def test_cleanup_command_removes_orphaned_variants(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        settings.LOCAL_MEDIA_ROOT = tmp_path

        orphan_name = "optimized/webp/md/avatars/2026/04/08/aa/bb/orphan.webp"
        orphan_path = Path(tmp_path) / orphan_name
        orphan_path.parent.mkdir(parents=True, exist_ok=True)
        orphan_path.write_bytes(b"orphan")

        call_command("cleanup_optimized_media_variants")

        assert not orphan_path.exists()
