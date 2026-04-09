from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath

from django.core.files.base import ContentFile
from django.db.models.fields.files import FieldFile
from PIL import Image, ImageOps, UnidentifiedImageError

ORIGINAL_IMAGE_PREFIX = "original"
OPTIMIZED_IMAGE_PREFIX = "optimized/webp"
OPTIMIZABLE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass(frozen=True)
class ImageVariantSpec:
    max_width: int
    max_height: int
    quality: int = 76
    method: int = 6


IMAGE_VARIANT_SPECS: dict[str, OrderedDict[str, ImageVariantSpec]] = {
    "avatars": OrderedDict(
        [
            ("sm", ImageVariantSpec(max_width=64, max_height=64, quality=74)),
            ("md", ImageVariantSpec(max_width=128, max_height=128, quality=76)),
            ("lg", ImageVariantSpec(max_width=256, max_height=256, quality=78)),
        ]
    ),
    "community_icons": OrderedDict(
        [
            ("sm", ImageVariantSpec(max_width=64, max_height=64, quality=74)),
            ("md", ImageVariantSpec(max_width=128, max_height=128, quality=76)),
            ("lg", ImageVariantSpec(max_width=256, max_height=256, quality=78)),
        ]
    ),
    "profile_banners": OrderedDict(
        [
            ("sm", ImageVariantSpec(max_width=800, max_height=320, quality=72)),
            ("md", ImageVariantSpec(max_width=1200, max_height=480, quality=74)),
            ("lg", ImageVariantSpec(max_width=1600, max_height=640, quality=76)),
        ]
    ),
    "community_banners": OrderedDict(
        [
            ("sm", ImageVariantSpec(max_width=800, max_height=320, quality=72)),
            ("md", ImageVariantSpec(max_width=1200, max_height=480, quality=74)),
            ("lg", ImageVariantSpec(max_width=1600, max_height=640, quality=76)),
        ]
    ),
    "post_images": OrderedDict(
        [
            ("sm", ImageVariantSpec(max_width=480, max_height=480, quality=72)),
            ("md", ImageVariantSpec(max_width=960, max_height=960, quality=74)),
            ("lg", ImageVariantSpec(max_width=1600, max_height=1600, quality=76)),
        ]
    ),
}

DEFAULT_VARIANT_SIZE_BY_NAMESPACE = {
    "avatars": "md",
    "community_icons": "md",
    "profile_banners": "lg",
    "community_banners": "lg",
    "post_images": "lg",
}


def _normalized_name(name: str) -> str:
    return name.lstrip("/").replace("\\", "/")


def is_original_image_name(name: str) -> bool:
    return _normalized_name(name).startswith(f"{ORIGINAL_IMAGE_PREFIX}/")


def is_optimized_variant_name(name: str) -> bool:
    return _normalized_name(name).startswith(f"{OPTIMIZED_IMAGE_PREFIX}/")


def _variant_parts(name: str) -> tuple[str, ...]:
    return PurePosixPath(_normalized_name(name)).parts


def _source_namespace(name: str) -> str:
    parts = _variant_parts(name)
    if not parts:
        return ""
    if parts[0] == ORIGINAL_IMAGE_PREFIX:
        return parts[1] if len(parts) > 1 else ""
    if len(parts) >= 4 and parts[0] == "optimized" and parts[1] == "webp":
        return parts[3]
    return parts[0]


def image_variant_specs_for_name(name: str) -> OrderedDict[str, ImageVariantSpec]:
    return IMAGE_VARIANT_SPECS.get(_source_namespace(name), OrderedDict())


def default_variant_size_for_name(name: str) -> str | None:
    return DEFAULT_VARIANT_SIZE_BY_NAMESPACE.get(_source_namespace(name))


def _relative_source_path(name: str) -> PurePosixPath:
    parts = _variant_parts(name)
    if not parts:
        return PurePosixPath()
    if parts[0] == ORIGINAL_IMAGE_PREFIX:
        return PurePosixPath(*parts[1:])
    if len(parts) >= 4 and parts[0] == "optimized" and parts[1] == "webp":
        return PurePosixPath(*parts[3:]).with_suffix(".webp")
    return PurePosixPath(*parts)


def original_image_name(source_name: str) -> str | None:
    normalized_name = _normalized_name(source_name)
    if not normalized_name:
        return None
    if is_original_image_name(normalized_name):
        return normalized_name
    namespace = _source_namespace(normalized_name)
    if namespace not in IMAGE_VARIANT_SPECS:
        return normalized_name
    return str(PurePosixPath(ORIGINAL_IMAGE_PREFIX) / _relative_source_path(normalized_name))


def variant_image_name(source_name: str, size: str | None = None) -> str | None:
    normalized_name = _normalized_name(source_name)
    if not normalized_name:
        return None
    size = size or default_variant_size_for_name(normalized_name)
    specs = image_variant_specs_for_name(normalized_name)
    if not size or size not in specs:
        return None
    relative_path = _relative_source_path(normalized_name).with_suffix(".webp")
    return str(PurePosixPath(OPTIMIZED_IMAGE_PREFIX) / size / relative_path)


def iter_variant_names(source_name: str) -> list[str]:
    specs = image_variant_specs_for_name(source_name)
    return [
        variant_name
        for size in specs
        if (variant_name := variant_image_name(source_name, size)) is not None
    ]


def variant_urls(field_file: FieldFile) -> OrderedDict[str, str]:
    urls: OrderedDict[str, str] = OrderedDict()
    if not field_file or not getattr(field_file, "name", ""):
        return urls
    for size in image_variant_specs_for_name(field_file.name):
        variant_name = variant_image_name(field_file.name, size)
        if variant_name:
            urls[size] = field_file.storage.url(variant_name)
    return urls


def optimized_image_url(field_file: FieldFile, *, size: str | None = None) -> str | None:
    if not field_file or not getattr(field_file, "name", ""):
        return None
    variant_name = variant_image_name(field_file.name, size=size)
    if not variant_name:
        return field_file.url
    return field_file.storage.url(variant_name)


def optimized_image_srcset(field_file: FieldFile) -> str:
    if not field_file or not getattr(field_file, "name", ""):
        return ""
    parts: list[str] = []
    for size, spec in image_variant_specs_for_name(field_file.name).items():
        variant_url = optimized_image_url(field_file, size=size)
        if variant_url:
            parts.append(f"{variant_url} {spec.max_width}w")
    return ", ".join(parts)


def _is_optimizable_name(name: str) -> bool:
    return Path(_normalized_name(name)).suffix.lower() in OPTIMIZABLE_EXTENSIONS


def _read_source_image_bytes(field_file: FieldFile) -> bytes | None:
    source_name = getattr(field_file, "name", "")
    if not source_name or not _is_optimizable_name(source_name):
        return None
    try:
        field_file.open("rb")
    except FileNotFoundError:
        return None
    try:
        return field_file.read()
    finally:
        field_file.close()


def _prepare_image(source_bytes: bytes):
    try:
        image = Image.open(BytesIO(source_bytes))
    except UnidentifiedImageError:
        return None
    if getattr(image, "is_animated", False):
        return None
    image = ImageOps.exif_transpose(image)
    has_alpha = "A" in image.getbands()
    return image.convert("RGBA" if has_alpha else "RGB")


def _save_single_variant(
    storage,
    source_name: str,
    prepared_image,
    *,
    size: str,
    spec: ImageVariantSpec,
    force: bool = False,
) -> str | None:
    variant_name = variant_image_name(source_name, size=size)
    if not variant_name:
        return None
    if not force and storage.exists(variant_name):
        return variant_name

    working_image = prepared_image.copy()
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    working_image.thumbnail((spec.max_width, spec.max_height), resample=resampling)

    buffer = BytesIO()
    working_image.save(
        buffer,
        format="WEBP",
        quality=spec.quality,
        method=spec.method,
    )
    buffer.seek(0)

    if storage.exists(variant_name):
        storage.delete(variant_name)
    storage.save(variant_name, ContentFile(buffer.read(), name=Path(variant_name).name))
    return variant_name


def ensure_optimized_images(field_file: FieldFile, *, force: bool = False) -> list[str]:
    if not field_file or not getattr(field_file, "name", ""):
        return []
    specs = image_variant_specs_for_name(field_file.name)
    if not specs:
        return []

    source_bytes = _read_source_image_bytes(field_file)
    if not source_bytes:
        return []
    prepared_image = _prepare_image(source_bytes)
    if prepared_image is None:
        return []

    created: list[str] = []
    for size, spec in specs.items():
        variant_name = _save_single_variant(
            field_file.storage,
            field_file.name,
            prepared_image,
            size=size,
            spec=spec,
            force=force,
        )
        if variant_name:
            created.append(variant_name)
    return created


def ensure_optimized_image(field_file: FieldFile, *, force: bool = False) -> str | None:
    if not field_file or not getattr(field_file, "name", ""):
        return None
    created = ensure_optimized_images(field_file, force=force)
    default_variant_name = variant_image_name(field_file.name)
    if default_variant_name in created:
        return default_variant_name
    return default_variant_name if default_variant_name and field_file.storage.exists(default_variant_name) else None


def delete_optimized_image(field_file: FieldFile) -> None:
    if not field_file or not getattr(field_file, "name", ""):
        return
    storage = field_file.storage
    for variant_name in iter_variant_names(field_file.name):
        if storage.exists(variant_name):
            storage.delete(variant_name)
