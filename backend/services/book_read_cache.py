"""File-signature caches for frequently requested textbook catalog data."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Callable


def _signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size
    except OSError:
        return None


class BookReadCache:
    """Thread-safe cache that invalidates automatically when backing files change."""

    def __init__(self):
        self._lock = threading.RLock()
        self._json: dict[str, tuple[tuple[int, int] | None, Any]] = {}
        self._pdfs: dict[str, tuple[tuple[int, int] | None, tuple[Path, ...]]] = {}
        self._index: dict[
            tuple[str, str, str],
            tuple[
                tuple[int, int] | None,
                tuple[int, int] | None,
                dict,
            ],
        ] = {}

    def clear(self) -> None:
        with self._lock:
            self._json.clear()
            self._pdfs.clear()
            self._index.clear()

    def read_json(self, path: Path, default: Any) -> Any:
        key = str(path.resolve())
        signature = _signature(path)
        with self._lock:
            cached = self._json.get(key)
            if cached and cached[0] == signature:
                return cached[1]
        try:
            value = json.loads(path.read_text(encoding="utf-8")) if signature else default
        except Exception:
            value = default
        with self._lock:
            self._json[key] = (signature, value)
        return value

    def list_pdfs(self, root: Path) -> list[Path]:
        root.mkdir(parents=True, exist_ok=True)
        key = str(root.resolve())
        signature = _signature(root)
        with self._lock:
            cached = self._pdfs.get(key)
            if cached and cached[0] == signature:
                return list(cached[1])
        files = tuple(root.glob("*.pdf"))
        with self._lock:
            self._pdfs[key] = (signature, files)
        return list(files)

    def index_stats(
        self,
        book_name: str,
        chapter_map_path: Path,
        lexical_path: Path,
        loader: Callable[[], dict],
    ) -> dict:
        key = (
            book_name,
            str(chapter_map_path.resolve()),
            str(lexical_path.resolve()),
        )
        map_signature = _signature(chapter_map_path)
        lexical_signature = _signature(lexical_path)
        with self._lock:
            cached = self._index.get(key)
            if (
                cached
                and cached[0] == map_signature
                and cached[1] == lexical_signature
            ):
                return cached[2]
        value = loader()
        with self._lock:
            self._index[key] = (
                map_signature,
                lexical_signature,
                value,
            )
        return value
