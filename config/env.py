from __future__ import annotations

import os


def env_str(key: str, default: str = "") -> str:
    return str(os.environ.get(key, default) or default)


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int = 0) -> int:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    return int(raw)


def env_float(key: str, default: float = 0.0) -> float:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    return float(raw)


def env_list(key: str, default: str = "", separator: str = ",") -> list[str]:
    raw = os.environ.get(key, default)
    if not raw:
        return []
    return [item.strip() for item in raw.split(separator) if item.strip()]
