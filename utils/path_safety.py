"""Helpers for keeping user-facing names safe when used in local paths."""
from __future__ import annotations

import re
from pathlib import Path

_INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_book_name(book_name: str, default: str = "default") -> str:
    name = Path(str(book_name or default)).name.strip()
    name = _INVALID_PATH_CHARS.sub("_", name).strip(". ")
    return (name or default)[:120]


def safe_child_path(root: str | Path, *parts: str | Path) -> Path:
    root_path = Path(root).resolve()
    path = root_path.joinpath(*parts).resolve()
    if path != root_path and root_path not in path.parents:
        raise ValueError(f"resolved path escapes root: {path}")
    return path