"""Shared byte, disk-space, and archive expansion limits."""
from __future__ import annotations

import os
import shutil
import stat
import zipfile
from pathlib import Path
from typing import BinaryIO


MIB = 1024 * 1024
GIB = 1024 * MIB


def _env_bytes(name: str, default: int) -> int:
    try:
        return max(MIB, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default

def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return max(1.0, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default



MAX_BOOK_PDF_BYTES = _env_bytes("KAOYAN_MAX_BOOK_PDF_BYTES", 512 * MIB)
MAX_EXERCISE_UPLOAD_BYTES = _env_bytes("KAOYAN_MAX_EXERCISE_UPLOAD_BYTES", 128 * MIB)
MAX_OUTPUT_ZIP_BYTES = _env_bytes("KAOYAN_MAX_OUTPUT_ZIP_BYTES", 2 * GIB)
MIN_FREE_DISK_BYTES = _env_bytes("KAOYAN_MIN_FREE_DISK_BYTES", 512 * MIB)

MAX_ARCHIVE_FILES = _env_int("KAOYAN_MAX_ARCHIVE_FILES", 100000)
MAX_ARCHIVE_EXPANDED_BYTES = _env_bytes("KAOYAN_MAX_ARCHIVE_EXPANDED_BYTES", 20 * GIB)
MAX_ARCHIVE_MEMBER_BYTES = _env_bytes("KAOYAN_MAX_ARCHIVE_MEMBER_BYTES", 4 * GIB)
MAX_ARCHIVE_COMPRESSION_RATIO = _env_float("KAOYAN_MAX_ARCHIVE_COMPRESSION_RATIO", 200.0)

MAX_DOCX_FILES = _env_int("KAOYAN_MAX_DOCX_FILES", 20000)
MAX_DOCX_EXPANDED_BYTES = _env_bytes("KAOYAN_MAX_DOCX_EXPANDED_BYTES", 512 * MIB)
MAX_DOCX_MEMBER_BYTES = _env_bytes("KAOYAN_MAX_DOCX_MEMBER_BYTES", 128 * MIB)


def format_bytes(value: int) -> str:
    if value >= GIB:
        return f"{value / GIB:.1f} GiB"
    return f"{value / MIB:.1f} MiB"


def ensure_disk_space(path: str | Path, required_bytes: int = 0) -> None:
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(root).free
    required = max(0, required_bytes) + MIN_FREE_DISK_BYTES
    if free < required:
        raise ValueError(
            f"Insufficient disk space: need {format_bytes(required)}, available {format_bytes(free)}"
        )


def copy_stream_limited(source: BinaryIO, destination: str | Path, *, max_bytes: int) -> int:
    """Copy an upload without ever retaining a partial oversized file."""
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        ensure_disk_space(target.parent)
        with target.open("xb") as output:
            while True:
                chunk = source.read(MIB)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"Upload exceeds size limit {format_bytes(max_bytes)}")
                ensure_disk_space(target.parent, len(chunk))
                output.write(chunk)
        return total
    except Exception:
        target.unlink(missing_ok=True)
        raise


def inspect_zip_limits(
    archive: zipfile.ZipFile,
    *,
    max_files: int = MAX_ARCHIVE_FILES,
    max_expanded_bytes: int = MAX_ARCHIVE_EXPANDED_BYTES,
    max_member_bytes: int = MAX_ARCHIVE_MEMBER_BYTES,
    max_ratio: float = MAX_ARCHIVE_COMPRESSION_RATIO,
) -> tuple[list[zipfile.ZipInfo], int]:
    infos = archive.infolist()
    files = [info for info in infos if not info.is_dir()]
    if len(files) > max_files:
        raise ValueError(f"Archive contains more than {max_files} files")

    expanded = 0
    for info in files:
        if info.flag_bits & 0x1:
            raise ValueError(f"Encrypted archive member is not supported: {info.filename}")
        mode = info.external_attr >> 16
        if mode and stat.S_ISLNK(mode):
            raise ValueError(f"Archive must not contain symbolic links: {info.filename}")
        if info.file_size > max_member_bytes:
            raise ValueError(
                f"Archive member exceeds {format_bytes(max_member_bytes)}: {info.filename}"
            )
        expanded += max(0, info.file_size)
        if expanded > max_expanded_bytes:
            raise ValueError(f"Archive expands beyond {format_bytes(max_expanded_bytes)}")
        if info.file_size >= MIB:
            ratio = info.file_size / max(1, info.compress_size)
            if ratio > max_ratio:
                raise ValueError(f"Suspicious archive compression ratio: {info.filename}")
    return infos, expanded


def validate_zip_paths(infos: list[zipfile.ZipInfo], target_dir: str | Path) -> None:
    root = Path(target_dir).resolve()
    for info in infos:
        name = info.filename.replace("\\", "/")
        if not name or name.startswith("/") or ".." in Path(name).parts:
            raise ValueError(f"Archive contains an unsafe path: {info.filename}")
        destination = (root / name).resolve()
        if destination != root and root not in destination.parents:
            raise ValueError(f"Archive path escapes target directory: {info.filename}")
