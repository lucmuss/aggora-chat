import io
import json
import os
import subprocess
import sys
from pathlib import Path

import boto3
import pytest
from botocore.config import Config
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from config.storage_backends import MediaStorage

REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeDestinationStorage:
    def __init__(self):
        self.existing = set()
        self.saved = []
        self.deleted = []

    def exists(self, name):
        return name in self.existing

    def save(self, name, file_handle):
        content = file_handle.read()
        self.saved.append((name, content))
        self.existing.add(name)
        return name

    def delete(self, name):
        self.deleted.append(name)
        self.existing.discard(name)


class TestMinioStorageSetup:
    def test_base_settings_switch_media_storage_to_s3_proxy_mode_by_default(self):
        env = os.environ.copy()
        env.update(
            {
                "USE_S3": "1",
                "AWS_ACCESS_KEY_ID": "minioadmin",
                "AWS_SECRET_ACCESS_KEY": "minioadmin123",
                "AWS_STORAGE_BUCKET_NAME": "agora-media",
                "AWS_S3_ENDPOINT_URL": "http://minio:9000",
                "AWS_S3_REGION_NAME": "us-east-1",
                "AWS_S3_SIGNATURE_VERSION": "s3v4",
                "AWS_S3_ADDRESSING_STYLE": "path",
                "AWS_QUERYSTRING_AUTH": "0",
                "AWS_S3_FILE_OVERWRITE": "0",
                "AWS_S3_VERIFY": "0",
            }
        )
        script = """
import json
import config.settings.base as base

print(json.dumps({
    "use_s3": base.USE_S3,
    "proxy_media": base.AWS_S3_PROXY_MEDIA,
    "default_backend": base.STORAGES["default"]["BACKEND"],
    "media_url": base.MEDIA_URL,
    "serve_media_files": base.SERVE_MEDIA_FILES,
    "bucket": base.AWS_STORAGE_BUCKET_NAME,
    "endpoint": base.AWS_S3_ENDPOINT_URL,
}))
"""

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)

        assert data["use_s3"] is True
        assert data["proxy_media"] is True
        assert data["default_backend"] == "config.storage_backends.MediaStorage"
        assert data["media_url"] == "/media/"
        assert data["serve_media_files"] is False
        assert data["bucket"] == "agora-media"
        assert data["endpoint"] == "http://minio:9000"

    def test_media_storage_builds_relative_proxy_urls_when_proxy_mode_enabled(self, settings):
        settings.MEDIA_URL = "/media/"
        settings.AWS_S3_PROXY_MEDIA = True

        storage = MediaStorage()

        assert storage.url("avatars/test image.png") == "/media/avatars/test%20image.png"
        assert storage.get_object_parameters("avatars/test-image.png")["CacheControl"] == "max-age=86400"

    def test_live_minio_bucket_is_reachable_when_enabled(self):
        if os.environ.get("MINIO_VERIFY_LIVE") != "1":
            pytest.skip("Set MINIO_VERIFY_LIVE=1 to run the live MinIO verification test.")

        client = boto3.client(
            "s3",
            endpoint_url=os.environ.get("MINIO_TEST_ENDPOINT", "http://127.0.0.1:19000"),
            aws_access_key_id=os.environ.get("MINIO_TEST_ACCESS_KEY", "minioadmin"),
            aws_secret_access_key=os.environ.get("MINIO_TEST_SECRET_KEY", "minioadmin123"),
            region_name=os.environ.get("MINIO_TEST_REGION", "us-east-1"),
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            verify=False,
        )

        response = client.head_bucket(Bucket=os.environ.get("MINIO_TEST_BUCKET", "agora-media"))

        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200


@pytest.mark.django_db
class TestMinioMigrationCommand:
    def test_migrate_media_to_object_storage_copies_referenced_files(self, settings, tmp_path, monkeypatch):
        settings.USE_S3 = True
        settings.LOCAL_MEDIA_ROOT = tmp_path

        avatar_dir = tmp_path / "avatars"
        avatar_dir.mkdir()
        avatar_path = avatar_dir / "avatar.png"
        avatar_path.write_bytes(b"avatar-bytes")

        user = User.objects.create_user(
            username="minio_case",
            email="minio_case@example.com",
            password="password123",
            handle="minio_case",
        )
        user.avatar = "avatars/avatar.png"
        user.save(update_fields=["avatar"])

        fake_storage = FakeDestinationStorage()
        monkeypatch.setattr(
            "apps.common.management.commands.migrate_media_to_object_storage.default_storage",
            fake_storage,
        )

        stdout = io.StringIO()
        call_command("migrate_media_to_object_storage", stdout=stdout)
        output = stdout.getvalue()

        assert fake_storage.saved == [("avatars/avatar.png", b"avatar-bytes")]
        assert "Total referenced files: 1" in output
        assert "Copied: 1" in output
        assert "Errors: 0" in output

    def test_migrate_media_to_object_storage_requires_s3_mode(self, settings):
        settings.USE_S3 = False

        with pytest.raises(CommandError, match="USE_S3 must be enabled before migrating media to object storage."):
            call_command("migrate_media_to_object_storage")
