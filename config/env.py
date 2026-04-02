from __future__ import annotations

import os


def _normalize_env_value(raw, default: str = ""):
    if raw is None:
        return default
    value = str(raw).strip()
    if not value:
        return default
    if value.lower() in {"null", "none", "undefined"}:
        return default
    if value.startswith("${") and value.endswith("}"):
        return default
    return value


def env_str(key: str, default: str = "") -> str:
    return _normalize_env_value(os.environ.get(key), default)


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    normalized = _normalize_env_value(raw, "")
    if not normalized:
        return default
    return normalized.lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int = 0) -> int:
    raw = _normalize_env_value(os.environ.get(key), "")
    if raw == "":
        return default
    return int(raw)


def env_float(key: str, default: float = 0.0) -> float:
    raw = _normalize_env_value(os.environ.get(key), "")
    if raw == "":
        return default
    return float(raw)


def env_list(key: str, default: str = "", separator: str = ",") -> list[str]:
    raw = _normalize_env_value(os.environ.get(key), default)
    if not raw:
        return []
    return [item.strip() for item in raw.split(separator) if item.strip()]
