from __future__ import annotations

from urllib.parse import urljoin

from django.conf import settings
from django.utils.encoding import filepath_to_uri
from storages.backends.s3boto3 import S3Boto3Storage


class MediaStorage(S3Boto3Storage):
    default_acl = None
    file_overwrite = getattr(settings, "AWS_S3_FILE_OVERWRITE", False)
    querystring_auth = getattr(settings, "AWS_QUERYSTRING_AUTH", False)

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("bucket_name", settings.AWS_STORAGE_BUCKET_NAME)
        super().__init__(*args, **kwargs)

    def get_object_parameters(self, name):
        params = super().get_object_parameters(name)
        normalized_name = name.lstrip("/")
        if normalized_name.startswith("optimized/webp/"):
            params.setdefault("CacheControl", "public, max-age=31536000, immutable")
        else:
            params.setdefault("CacheControl", "public, max-age=86400")
        return params

    def url(self, name, parameters=None, expire=None, http_method=None):
        normalized_name = filepath_to_uri(name.lstrip("/"))
        if getattr(settings, "AWS_S3_PROXY_MEDIA", False):
            return urljoin(settings.MEDIA_URL, normalized_name)

        public_base_url = getattr(settings, "AWS_S3_PUBLIC_BASE_URL", "").rstrip("/")
        if public_base_url:
            return urljoin(f"{public_base_url}/{self.bucket_name}/", normalized_name)
        return super().url(name, parameters=parameters, expire=expire, http_method=http_method)
